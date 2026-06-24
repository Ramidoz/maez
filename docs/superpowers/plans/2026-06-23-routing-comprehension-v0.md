# Routing Comprehension v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a shadow-first comprehension gate that runs only when Layer0 is about to use `WEB_SEARCH`, then vetoes clearly personal/relational or receipt-answerable follow-up turns without blocking genuine current-world requests.

**Architecture:** The slice adds a small typed external-info eligibility judge at the dispatcher seam in `core/brain/brain_loop.py`, after Layer0/repair selects `WEB_SEARCH` and before `ExternalFanout.run()` can call SearXNG. The judge is a brain-call backed, injectable component with a strict 4-way schema; unit tests patch it so no tests call a model. A separate provenance rail extends the existing `/receipts` store so a thread follow-up can answer from the prior retained web receipt instead of searching again.

**Tech Stack:** Python 3.11, unittest, dataclasses, `core.routing.llm_client`, existing dispatcher `CompositionSpec`, existing `core.routing.attribution_render` receipt store.

---

## File Map

- Create `core/routing/routing_comprehension.py`
  - Owns flags, typed decisions, prompt rendering, JSON parsing, content-light receipt rendering, spec-veto helper, and prior-receipt context rendering.
  - Must contain no keyword/regex intent matching. The only decision-maker is the injected/LLM judge.
- Modify `core/brain/brain_loop.py`
  - Calls the judge only if `WEB_SEARCH` is selected.
  - Logs shadow receipt.
  - Under `MAEZ_ROUTING_COMPREHENSION_ENABLED=1`, removes `WEB_SEARCH` only for confident veto decisions.
  - Threads prior receipt context into the dispatcher prompt for `thread_followup_answerable`.
- Modify `core/routing/attribution_render.py`
  - Extends retained receipts with optional content-light `observation` metadata and adds a helper for last web receipt context.
  - Keeps existing `/receipts` behavior compatible.
- Create `tests/test_routing_comprehension.py`
  - Pure module tests: parser, prompt bounds, no-keyword structural guard, spec-veto helper, receipt context.
- Modify `tests/test_brain_loop.py`
  - Dispatcher seam tests for default-off, shadow-only, enabled-veto, still-search, and thread-followup receipt path.
- Modify `tests/test_attribution_render.py`
  - Backward compatibility for `retain_receipt` and new receipt metadata helper.
- Create `docs/handoffs/2026-06-23-routing-comprehension-v0-handoff.md`
  - Branch/tip/tests, predicted effect, witness set, and review anchors.

---

### Task 0: Proof Gate — Real Seam, Trigger, and Receipt

**Files:**
- Read-only: `core/brain/brain_loop.py`
- Read-only: `core/dispatcher/layer0.py`
- Read-only: `core/routing/attribution_render.py`
- Read-only: `logs/maez.log`
- Create: `docs/proofs/2026-06-23-routing-comprehension-v0-task0.md`

- [ ] **Step 1: Prove the live wound from logs**

Run:

```bash
cd /home/rohit/maez
rg -n -i \
  "Pretty nice\\. I did legs|What did you check online|Web search \\(searxng sense\\)|dispatcher_layer0_emit|routing_observation" \
  logs/maez.log | tail -120
```

Expected: shows the vulnerable turn and the follow-up both produce `Web search (searxng sense)` and `routing_observation path=dispatcher source=WEB_SEARCH tool=web_search status=success spec_match_score=1.000 outcome_quality=structured_evidence utterance_shape=unknown`.

- [ ] **Step 2: Prove the first trigger is Layer0 current-world `today`**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python - <<'PY'
from core.dispatcher.layer0 import _is_current_world_request
from skills.web_search import needs_web_search

cases = [
    "Pretty nice. I did legs today. I have always been insecure about my legs.",
    "I did legs today",
    "I have always been insecure about my legs",
    "What's the latest on OpenAI today?",
]
for case in cases:
    print(repr(case), "layer0_current=", _is_current_world_request(case), "legacy_needs_web=", needs_web_search(case))
PY
```

Expected:

```text
'Pretty nice. I did legs today. I have always been insecure about my legs.' layer0_current= True legacy_needs_web= True
'I did legs today' layer0_current= True legacy_needs_web= True
'I have always been insecure about my legs' layer0_current= False legacy_needs_web= False
"What's the latest on OpenAI today?" layer0_current= True legacy_needs_web= True
```

- [ ] **Step 3: Prove the second trigger is Layer0 content/freshness `online`**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python - <<'PY'
from core.dispatcher.layer0 import _CONTENT_ANCHOR_RE

cases = [
    "What did you check online for that?",
    "What did you check for that?",
]
for case in cases:
    print(repr(case), "content_anchor=", bool(_CONTENT_ANCHOR_RE.search(case)))
PY
```

Expected: `online` case is `True`; no-`online` case is `False`.

- [ ] **Step 4: Prove insertion point is before external fanout**

Run:

```bash
cd /home/rohit/maez
sed -n '700,815p' core/brain/brain_loop.py
```

Expected: shows this order:

1. Layer2 repair resolves `spec`.
2. `fanout_generation_id` and `conversation_state` are created.
3. `Layer1Fanout` and `ExternalFanout` are created.
4. `_emit_search_progress` runs.
5. `external_fanout.run` starts.

Task 2 must insert the comprehension call after repair and before `_emit_search_progress`.

- [ ] **Step 5: Prove current receipt rail**

Run:

```bash
cd /home/rohit/maez
sed -n '1,120p' core/routing/attribution_render.py
rg -n "pop_turn_evidence|retain_receipt|render_natural" daemon/maez_daemon.py tests/test_attribution_render.py
```

Expected:

- `retain_receipt(chat_id, marked=<reply>, sources=<source-list>)` stores marked reply + sources.
- `pop_turn_evidence(chat_id)` has `observation` with query/diagnostic metadata for the current turn.
- The daemon calls `retain_receipt` after focused/grounding work, so Task 4 can extend it with optional observation metadata and read it on the next turn.

- [ ] **Step 6: Write proof doc**

Create `docs/proofs/2026-06-23-routing-comprehension-v0-task0.md`:

```markdown
# Routing Comprehension v0 Task 0 Proof

## Wound

- First wound turn: personal statement containing `today` routed to `WEB_SEARCH`.
- Follow-up wound turn: `online` follow-up routed to `WEB_SEARCH`.

## Trigger

- First turn: Layer0 `_is_current_world_request` returns true because of current-world marker `today`.
- Follow-up: Layer0 content/freshness path sees `online`.
- Learned routing does not save this because request class is exact-utterance hash in v0 and novel turns produce `prior=None`.

## Seam

- Insert after Layer2 repair resolves `spec`.
- Insert before `_emit_search_progress` and `ExternalFanout.run`.
- Veto modifies only `WEB_SEARCH`; other tools are out of v0 scope.

## Receipt Rail

- Extend `retain_receipt` with optional observation metadata from `pop_turn_evidence`.
- Use last retained web receipt for `thread_followup_answerable`; otherwise render an honest no-receipt context.

## STOP/GO

GO if all above are verified. STOP if the dispatcher order, receipt seam, or trigger evidence differs from this proof.
```

- [ ] **Step 7: Commit proof**

```bash
git add docs/proofs/2026-06-23-routing-comprehension-v0-task0.md
git commit -m "docs(routing): prove comprehension veto seam"
```

---

### Task 1: Pure Routing Comprehension Module

**Files:**
- Create: `core/routing/routing_comprehension.py`
- Create: `tests/test_routing_comprehension.py`

- [ ] **Step 1: Write failing pure-module tests**

Create `tests/test_routing_comprehension.py`:

```python
from __future__ import annotations

import inspect
import unittest
from dataclasses import replace

from core.dispatcher.spec import (
    CompositionHint,
    CompositionSpec,
    ExternalSource,
    InventoryWitness,
    ProvenanceFraming,
    SubstrateSource,
)
from core.routing import routing_comprehension as rc


class RoutingComprehensionPureTests(unittest.TestCase):
    def test_parse_valid_json_decision(self):
        out = rc.parse_judge_response(
            '{"decision":"personal_or_relational","confidence":0.91,'
            '"reason_code":"owner_sharing_personal_state"}'
        )
        self.assertEqual(out.decision, rc.Decision.PERSONAL_OR_RELATIONAL)
        self.assertEqual(out.confidence, 0.91)
        self.assertEqual(out.reason_code, "owner_sharing_personal_state")

    def test_parse_invalid_json_fails_to_ambiguous(self):
        out = rc.parse_judge_response("not json")
        self.assertEqual(out.decision, rc.Decision.AMBIGUOUS)
        self.assertEqual(out.reason_code, "parse_error")

    def test_prompt_is_bounded_and_contains_no_witness_phrases(self):
        ctx = rc.JudgeContext(
            current_turn="x" * 5000,
            dialogue_tail=("a" * 1000, "b" * 1000, "c" * 1000, "d" * 1000, "e" * 1000),
            trigger=rc.SearchTrigger(source="WEB_SEARCH", reason="current_world_request"),
            prior_receipt=rc.PriorToolReceipt(
                kind="web_search",
                query="q" * 1000,
                sources=("https://example.test/a",),
                diagnostic_id="diag",
            ),
        )
        prompt = rc.render_judge_prompt(ctx)
        self.assertLessEqual(len(prompt), 6000)
        lower = prompt.lower()
        for forbidden in ("insecure", "legs", "nvidia", "openai", "latest price"):
            self.assertNotIn(forbidden, lower)

    def test_structural_no_keyword_or_regex_intent_matching(self):
        src = inspect.getsource(rc)
        self.assertNotIn("import re", src)
        self.assertNotIn("re.", src)
        self.assertNotIn("_RE", src)
        for forbidden in ("insecure", "legs", "nvidia", "openai", "i feel", "today"):
            self.assertNotIn(forbidden, src.lower())

    def test_veto_removes_web_search_keeps_substrate(self):
        spec = _spec(
            substrate_sources=[SubstrateSource.TELEGRAM_SEMANTIC],
            external_sources=[ExternalSource.WEB_SEARCH],
            hint=CompositionHint.PARALLEL,
            framing=ProvenanceFraming.HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES,
        )
        decision = rc.JudgeDecision(
            decision=rc.Decision.PERSONAL_OR_RELATIONAL,
            confidence=0.95,
            reason_code="owner_sharing_personal_state",
        )
        out = rc.apply_web_search_veto(spec, decision)
        self.assertEqual(out.external_sources, [])
        self.assertEqual(out.substrate_sources, [SubstrateSource.TELEGRAM_SEMANTIC])
        self.assertEqual(out.composition_hint, CompositionHint.SUBSTRATE_ONLY)
        self.assertEqual(out.provenance_framing, ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION)

    def test_non_veto_decisions_leave_spec_identity(self):
        spec = _spec(external_sources=[ExternalSource.WEB_SEARCH])
        for decision in (
            rc.Decision.EXTERNAL_INFO_REQUESTED,
            rc.Decision.AMBIGUOUS,
        ):
            out = rc.apply_web_search_veto(
                spec,
                rc.JudgeDecision(decision=decision, confidence=0.5, reason_code="x"),
            )
            self.assertIs(out, spec)

    def test_content_light_receipt_excludes_turn_text(self):
        receipt = rc.shadow_receipt(
            surface="telegram_surface",
            chat_id="123456",
            decision=rc.JudgeDecision(
                decision=rc.Decision.PERSONAL_OR_RELATIONAL,
                confidence=0.94,
                reason_code="owner_sharing_personal_state",
            ),
            trigger=rc.SearchTrigger(source="WEB_SEARCH", reason="current_world_request"),
            enabled=False,
            veto_applied=False,
        )
        self.assertIn("routing_comprehension", receipt)
        self.assertIn("decision=personal_or_relational", receipt)
        self.assertIn("trigger=current_world_request", receipt)
        self.assertNotIn("123456", receipt)
        self.assertNotIn("insecure", receipt.lower())


def _spec(
    *,
    substrate_sources=None,
    external_sources=None,
    hint=CompositionHint.FRESH_ONLY,
    framing=ProvenanceFraming.FRESH_ONLY,
) -> CompositionSpec:
    return CompositionSpec(
        substrate_sources=list(substrate_sources or []),
        external_sources=list(external_sources or []),
        composition_hint=hint,
        provenance_framing=framing,
        inventory_witness=InventoryWitness.MIXED,
        source_availability={},
        availability_limitations=[],
        freshness_window=None,
        trust_scope_union=None,
    )
```

- [ ] **Step 2: Run tests to verify fail**

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_routing_comprehension -v
```

Expected: FAIL with `ImportError` or missing `core.routing.routing_comprehension`.

- [ ] **Step 3: Implement module**

Create `core/routing/routing_comprehension.py`:

```python
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from core.dispatcher.spec import (
    CompositionHint,
    CompositionSpec,
    ExternalSource,
    ProvenanceFraming,
)

logger = logging.getLogger(__name__)

_TRUE = {"1", "true", "yes", "on"}
_MAX_TURN_CHARS = 900
_MAX_DIALOGUE_TURNS = 4
_MAX_DIALOGUE_CHARS = 600
_MAX_RECEIPT_QUERY_CHARS = 300
_MAX_REASON_CHARS = 80


class Decision(StrEnum):
    EXTERNAL_INFO_REQUESTED = "external_info_requested"
    PERSONAL_OR_RELATIONAL = "personal_or_relational"
    THREAD_FOLLOWUP_ANSWERABLE = "thread_followup_answerable"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class SearchTrigger:
    source: str
    reason: str


@dataclass(frozen=True)
class PriorToolReceipt:
    kind: str
    query: str | None = None
    sources: tuple[str, ...] = ()
    diagnostic_id: str | None = None


@dataclass(frozen=True)
class JudgeContext:
    current_turn: str
    dialogue_tail: tuple[str, ...] = ()
    trigger: SearchTrigger | None = None
    prior_receipt: PriorToolReceipt | None = None


@dataclass(frozen=True)
class JudgeDecision:
    decision: Decision
    confidence: float
    reason_code: str

    @property
    def vetoes_web_search(self) -> bool:
        return self.decision in {
            Decision.PERSONAL_OR_RELATIONAL,
            Decision.THREAD_FOLLOWUP_ANSWERABLE,
        }


class EligibilityJudge(Protocol):
    def decide(self, context: JudgeContext) -> JudgeDecision:
        raise NotImplementedError


def shadow_enabled() -> bool:
    return (os.environ.get("MAEZ_ROUTING_COMPREHENSION_SHADOW") or "").strip().lower() in _TRUE


def enabled() -> bool:
    return (os.environ.get("MAEZ_ROUTING_COMPREHENSION_ENABLED") or "").strip().lower() in _TRUE


def any_enabled() -> bool:
    return shadow_enabled() or enabled()


def parse_judge_response(raw: str) -> JudgeDecision:
    try:
        text = (raw or "").strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()
        payload = json.loads(text)
        decision = Decision(str(payload.get("decision") or Decision.AMBIGUOUS))
        confidence = max(0.0, min(1.0, float(payload.get("confidence", 0.0))))
        reason_code = _compact_reason(payload.get("reason_code") or "model_decision")
        return JudgeDecision(decision=decision, confidence=confidence, reason_code=reason_code)
    except Exception:
        return JudgeDecision(
            decision=Decision.AMBIGUOUS,
            confidence=0.0,
            reason_code="parse_error",
        )


def render_judge_prompt(context: JudgeContext) -> str:
    tail = tuple(context.dialogue_tail or ())[-_MAX_DIALOGUE_TURNS:]
    tail_block = "\n".join(
        f"- {_clip(str(item), _MAX_DIALOGUE_CHARS)}" for item in tail if str(item).strip()
    )
    receipt = context.prior_receipt
    if receipt is None:
        receipt_block = "none"
    else:
        receipt_block = (
            f"kind={_clip(receipt.kind, 60)}; "
            f"query={_clip(receipt.query or '', _MAX_RECEIPT_QUERY_CHARS)}; "
            f"sources={len(receipt.sources)}; "
            f"diagnostic_id={_clip(receipt.diagnostic_id or '', 80)}"
        )
    trigger = context.trigger or SearchTrigger(source="WEB_SEARCH", reason="unknown")
    return (
        "You are a routing comprehension judge. Decide whether the owner is actually "
        "asking Maez to seek new external information before a WEB_SEARCH runs.\n\n"
        "Return ONLY JSON with keys: decision, confidence, reason_code.\n"
        "Allowed decision values:\n"
        "- external_info_requested: the owner is asking for new outside/current information.\n"
        "- personal_or_relational: the owner is sharing or relating, not asking Maez to look outside.\n"
        "- thread_followup_answerable: the owner asks about the immediately prior exchange or tool use.\n"
        "- ambiguous: uncertain; let search run.\n\n"
        "High precision rule: if uncertain, choose ambiguous. Do not infer from isolated words; "
        "read the whole turn and the immediate thread.\n\n"
        f"PROPOSED_TOOL: {trigger.source}\n"
        f"PROPOSED_TRIGGER: {_clip(trigger.reason, 180)}\n\n"
        f"RECENT_TOOL_RECEIPT: {receipt_block}\n\n"
        f"RECENT_DIALOGUE:\n{tail_block or 'none'}\n\n"
        f"CURRENT_OWNER_TURN:\n{_clip(context.current_turn, _MAX_TURN_CHARS)}"
    )[:6000]


class LlmEligibilityJudge:
    def decide(self, context: JudgeContext) -> JudgeDecision:
        from core import llm_client
        from core.model_config import PRIMARY_MODEL

        try:
            response = llm_client.chat(
                model=PRIMARY_MODEL,
                messages=[
                    {"role": "system", "content": "Return strict JSON only."},
                    {"role": "user", "content": render_judge_prompt(context)},
                ],
                think=False,
                options={"temperature": 0.0, "num_predict": 120},
            )
            return parse_judge_response(response.message.content or "")
        except Exception as exc:
            logger.debug("routing comprehension judge unavailable: %s", exc)
            return JudgeDecision(
                decision=Decision.AMBIGUOUS,
                confidence=0.0,
                reason_code="judge_unavailable",
            )


def default_judge() -> EligibilityJudge:
    return LlmEligibilityJudge()


def apply_web_search_veto(spec: CompositionSpec, decision: JudgeDecision) -> CompositionSpec:
    if not decision.vetoes_web_search:
        return spec
    if ExternalSource.WEB_SEARCH not in list(getattr(spec, "external_sources", ()) or ()):
        return spec
    external = [
        source for source in list(spec.external_sources or [])
        if source != ExternalSource.WEB_SEARCH
    ]
    substrate = list(spec.substrate_sources or [])
    if external:
        return CompositionSpec(
            substrate_sources=substrate,
            external_sources=external,
            composition_hint=spec.composition_hint,
            provenance_framing=spec.provenance_framing,
            inventory_witness=spec.inventory_witness,
            source_availability=dict(spec.source_availability or {}),
            availability_limitations=list(spec.availability_limitations or []),
            freshness_window=spec.freshness_window,
            trust_scope_union=spec.trust_scope_union,
        )
    return CompositionSpec(
        substrate_sources=substrate,
        external_sources=[],
        composition_hint=CompositionHint.SUBSTRATE_ONLY,
        provenance_framing=ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION,
        inventory_witness=spec.inventory_witness,
        source_availability=dict(spec.source_availability or {}),
        availability_limitations=list(spec.availability_limitations or []),
        freshness_window=spec.freshness_window,
        trust_scope_union=spec.trust_scope_union,
    )


def shadow_receipt(
    *,
    surface: str,
    chat_id: str | None,
    decision: JudgeDecision,
    trigger: SearchTrigger,
    enabled: bool,
    veto_applied: bool,
) -> str:
    del chat_id
    return (
        "routing_comprehension "
        f"surface={surface} "
        f"decision={decision.decision.value} "
        f"confidence={decision.confidence:.3f} "
        f"reason={decision.reason_code} "
        f"trigger={_compact_reason(trigger.reason)} "
        f"enabled={bool(enabled)} "
        f"veto_applied={bool(veto_applied)}"
    )


def receipt_context_text(receipt: PriorToolReceipt | None) -> str:
    if receipt is None:
        return (
            "=== PRIOR TOOL RECEIPT ===\n"
            "The owner is asking about prior tool use, but no retained web-search receipt "
            "is available for this chat. Answer that honestly; do not invent a search."
        )
    query = _clip(receipt.query or "", _MAX_RECEIPT_QUERY_CHARS) or "unknown query"
    sources = "\n".join(f"- {url}" for url in receipt.sources[:5]) or "- none retained"
    return (
        "=== PRIOR TOOL RECEIPT ===\n"
        f"Prior tool: {receipt.kind}\n"
        f"Prior query: {query}\n"
        f"Diagnostic id: {receipt.diagnostic_id or 'unknown'}\n"
        f"Sources retained:\n{sources}\n"
        "If the owner asks what you checked, answer from this receipt. Do not search again."
    )


def _clip(value: str, limit: int) -> str:
    value = str(value or "").strip()
    return value if len(value) <= limit else value[: max(0, limit - 1)].rstrip() + "…"


def _compact_reason(value: str) -> str:
    value = "".join(ch if ch.isalnum() or ch in {"_", "-", "."} else "_" for ch in str(value or ""))
    value = value.strip("_") or "unspecified"
    return value[:_MAX_REASON_CHARS]
```

- [ ] **Step 4: Run tests to verify pass**

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_routing_comprehension -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/routing/routing_comprehension.py tests/test_routing_comprehension.py
git commit -m "feat(routing): add comprehension judge contract"
```

---

### Task 2: Dispatcher Seam — Shadow-Only Receipt, No Behavior Change

**Files:**
- Modify: `core/brain/brain_loop.py`
- Modify: `tests/test_brain_loop.py`

- [ ] **Step 1: Write failing seam tests**

Append to `tests/test_brain_loop.py`:

```python
class RoutingComprehensionShadow(unittest.TestCase):
    def _web_spec(self):
        from core.dispatcher.spec import (
            CompositionHint,
            CompositionSpec,
            ExternalSource,
            InventoryWitness,
            ProvenanceFraming,
            SourceAvailability,
            SubstrateSource,
        )
        return CompositionSpec(
            substrate_sources=[SubstrateSource.TELEGRAM_SEMANTIC],
            external_sources=[ExternalSource.WEB_SEARCH],
            composition_hint=CompositionHint.PARALLEL,
            provenance_framing=ProvenanceFraming.HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES,
            inventory_witness=InventoryWitness.MIXED,
            source_availability={
                SubstrateSource.TELEGRAM_SEMANTIC: SourceAvailability.EXECUTABLE_PRESENT,
                ExternalSource.WEB_SEARCH: SourceAvailability.EXECUTABLE_PRESENT,
            },
            availability_limitations=[],
            freshness_window=None,
            trust_scope_union=None,
        )

    def test_default_off_never_calls_comprehension_judge(self):
        from core import brain_loop

        seen = {}
        spec = self._web_spec()

        with self._patched_dispatcher(brain_loop, spec, seen), (
            patch.dict(os.environ, {
                "MAEZ_RECALL_TRIAD_ENABLED": "1",
                "MAEZ_ROUTING_COMPREHENSION_SHADOW": "0",
                "MAEZ_ROUTING_COMPREHENSION_ENABLED": "0",
            }),
            patch("core.routing.routing_comprehension.default_judge",
                  side_effect=AssertionError("judge must not run")),
        ):
            result = brain_loop.run_brain_loop(
                "I did legs today",
                action_engine=object(),
                get_pipeline=lambda: None,
                surface="telegram_surface",
                chat_id="chat",
            )

        self.assertEqual(result, "MERGED")
        self.assertEqual(seen["external_sources"], ["WEB_SEARCH"])

    def test_shadow_logs_decision_but_external_search_still_runs(self):
        from core import brain_loop
        from core.routing import routing_comprehension as rc

        seen = {}
        spec = self._web_spec()

        class FakeJudge:
            def decide(self, context):
                seen["judge_context"] = context
                return rc.JudgeDecision(
                    decision=rc.Decision.PERSONAL_OR_RELATIONAL,
                    confidence=0.96,
                    reason_code="owner_sharing_personal_state",
                )

        with self._patched_dispatcher(brain_loop, spec, seen), (
            patch.dict(os.environ, {
                "MAEZ_RECALL_TRIAD_ENABLED": "1",
                "MAEZ_ROUTING_COMPREHENSION_SHADOW": "1",
                "MAEZ_ROUTING_COMPREHENSION_ENABLED": "0",
            }),
            patch("core.routing.routing_comprehension.default_judge", return_value=FakeJudge()),
        ):
            with self.assertLogs("core.routing.routing_comprehension", level="INFO") as logs:
                result = brain_loop.run_brain_loop(
                    "I did legs today",
                    action_engine=object(),
                    get_pipeline=lambda: None,
                    surface="telegram_surface",
                    chat_id="chat",
                    chat_history=[{"content": "rohit: Hey\nmaez: Hi"}],
                )

        self.assertEqual(result, "MERGED")
        self.assertEqual(seen["external_sources"], ["WEB_SEARCH"])
        self.assertIn("decision=personal_or_relational", "\n".join(logs.output))
        self.assertEqual(seen["judge_context"].current_turn, "I did legs today")
        self.assertTrue(seen["judge_context"].dialogue_tail)

    from contextlib import contextmanager

    @contextmanager
    def _patched_dispatcher(self, brain_loop, spec, seen):
        from types import SimpleNamespace
        from core.dispatcher.external_sources import ExternalFanoutResult

        class FakeLayer0:
            def __init__(self, *, index):
                pass
            def emit_spec(self, user_text, *, surface, inventory):
                return spec

        class FakeLayer1:
            def __init__(self, *, adapters, branch_timeout_s=None, global_deadline_s=None):
                pass
            def run(self, spec, *, utterance, conversation_state, fanout_generation_id=None):
                return SimpleNamespace(
                    branch_results=(),
                    recall_blocks=(),
                    fanout_generation_id=fanout_generation_id,
                    sealed_at=1.0,
                    budget_events=(),
                )

        class FakeExternalFanout:
            def run(self, spec, *, utterance, conversation_state, fanout_generation_id):
                seen["external_sources"] = [source.value for source in spec.external_sources]
                return ExternalFanoutResult(
                    fanout_generation_id=fanout_generation_id,
                    sealed_at=1.0,
                    branch_results=(),
                    fresh_blocks=(),
                    availability_limitations=(),
                )

        class FakeFSM:
            def apply_repair(self, **kwargs):
                return kwargs["current_spec"]
            def record_completed_spec(self, **kwargs):
                seen["recorded_spec"] = kwargs["spec"]

        def fake_merge(spec_arg, layer1_result, external_result, **kwargs):
            return SimpleNamespace(
                prompt_block="MERGED",
                effective_spec=spec_arg,
                refusal_reason=None,
                audit_envelope={},
                recall_items=(),
                source_summaries=(),
                fresh_attempt_outcome="ALL_SUCCEEDED",
            )

        with (
            patch.object(brain_loop, "_dispatcher_index", return_value=object()),
            patch.object(brain_loop, "_dispatcher_repair_fsm", return_value=FakeFSM()),
            patch("core.dispatcher.layer0.Layer0Dispatcher", FakeLayer0),
            patch("core.dispatcher.layer1.Layer1Fanout", FakeLayer1),
            patch("core.dispatcher.external_sources.ExternalFanout", return_value=FakeExternalFanout()),
            patch("core.dispatcher.merge.merge_fanout_results", side_effect=fake_merge),
            patch("core.routing.observation.record_dispatcher_turn_observation"),
        ):
            yield
```

- [ ] **Step 2: Run tests to verify fail**

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_brain_loop.RoutingComprehensionShadow -v
```

Expected: FAIL because `routing_comprehension.default_judge` is not called/logged.

- [ ] **Step 3: Implement seam helper in `brain_loop.py`**

In `core/brain/brain_loop.py`, after the `conversation_state` dictionary is created and before `Layer1Fanout`, add:

```python
    _routing_comprehension_decision = None
    _routing_comprehension_trigger = None
    _routing_comprehension_receipt = None
    try:
        from core.dispatcher.spec import ExternalSource as _RCExternalSource
        from core.routing import routing_comprehension as _routing_comprehension

        if (
            _routing_comprehension.any_enabled()
            and _RCExternalSource.WEB_SEARCH in list(getattr(spec, "external_sources", ()) or ())
        ):
            _routing_comprehension_trigger = _routing_comprehension.SearchTrigger(
                source="WEB_SEARCH",
                reason=_routing_comprehension_trigger_reason(layer0_spec, spec),
            )
            _routing_comprehension_context = _routing_comprehension.JudgeContext(
                current_turn=user_text,
                dialogue_tail=_routing_comprehension_dialogue_tail(chat_history),
                trigger=_routing_comprehension_trigger,
                prior_receipt=None,
            )
            _routing_comprehension_decision = (
                _routing_comprehension.default_judge().decide(
                    _routing_comprehension_context
                )
            )
            _routing_comprehension_receipt = _routing_comprehension.shadow_receipt(
                surface=surface,
                chat_id=chat_id,
                decision=_routing_comprehension_decision,
                trigger=_routing_comprehension_trigger,
                enabled=_routing_comprehension.enabled(),
                veto_applied=False,
            )
            logging.getLogger("core.routing.routing_comprehension").info(
                _routing_comprehension_receipt
            )
    except Exception as _routing_comprehension_exc:
        logging.getLogger("core.routing.routing_comprehension").debug(
            "routing comprehension skipped: %s",
            _routing_comprehension_exc,
        )
        _routing_comprehension_decision = None
```

Near the dispatcher helper functions in `core/brain/brain_loop.py`, add:

```python
def _routing_comprehension_dialogue_tail(chat_history) -> tuple[str, ...]:
    if not chat_history:
        return ()
    out: list[str] = []
    for exchange in list(chat_history)[-4:]:
        if isinstance(exchange, dict):
            text = str(exchange.get("content") or "").strip()
        else:
            text = str(exchange or "").strip()
        if text:
            out.append(text[:700])
    return tuple(out)


def _routing_comprehension_trigger_reason(layer0_spec, spec) -> str:
    try:
        if getattr(layer0_spec, "to_dict", None):
            original = layer0_spec.to_dict()
        else:
            original = {}
        if getattr(spec, "composition_hint", None):
            return str(getattr(spec.composition_hint, "value", spec.composition_hint))
        return str(original.get("composition_hint") or "web_search_selected")
    except Exception:
        return "web_search_selected"
```

- [ ] **Step 4: Run tests**

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_brain_loop.RoutingComprehensionShadow tests.test_routing_comprehension -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/brain/brain_loop.py tests/test_brain_loop.py
git commit -m "feat(routing): shadow comprehension before web search"
```

---

### Task 3: Enabled Veto for Personal/Relational Search Misfires

**Files:**
- Modify: `core/brain/brain_loop.py`
- Modify: `tests/test_brain_loop.py`

- [ ] **Step 1: Add failing enabled-veto tests**

Append to `RoutingComprehensionShadow` in `tests/test_brain_loop.py`:

```python
    def test_enabled_personal_decision_removes_web_search_before_fanout(self):
        from core import brain_loop
        from core.routing import routing_comprehension as rc

        seen = {}
        spec = self._web_spec()

        class FakeJudge:
            def decide(self, context):
                return rc.JudgeDecision(
                    decision=rc.Decision.PERSONAL_OR_RELATIONAL,
                    confidence=0.97,
                    reason_code="owner_sharing_personal_state",
                )

        with self._patched_dispatcher(brain_loop, spec, seen), (
            patch.dict(os.environ, {
                "MAEZ_RECALL_TRIAD_ENABLED": "1",
                "MAEZ_ROUTING_COMPREHENSION_SHADOW": "0",
                "MAEZ_ROUTING_COMPREHENSION_ENABLED": "1",
            }),
            patch("core.routing.routing_comprehension.default_judge", return_value=FakeJudge()),
        ):
            with self.assertLogs("core.routing.routing_comprehension", level="INFO") as logs:
                result = brain_loop.run_brain_loop(
                    "Pretty nice. I did legs today. I have always been insecure about my legs.",
                    action_engine=object(),
                    get_pipeline=lambda: None,
                    surface="telegram_surface",
                    chat_id="chat",
                )

        self.assertEqual(result, "MERGED")
        self.assertEqual(seen["external_sources"], [])
        self.assertIn("veto_applied=True", "\n".join(logs.output))

    def test_enabled_external_info_decision_keeps_web_search(self):
        from core import brain_loop
        from core.routing import routing_comprehension as rc

        seen = {}
        spec = self._web_spec()

        class FakeJudge:
            def decide(self, context):
                return rc.JudgeDecision(
                    decision=rc.Decision.EXTERNAL_INFO_REQUESTED,
                    confidence=0.98,
                    reason_code="owner_requests_current_data",
                )

        with self._patched_dispatcher(brain_loop, spec, seen), (
            patch.dict(os.environ, {
                "MAEZ_RECALL_TRIAD_ENABLED": "1",
                "MAEZ_ROUTING_COMPREHENSION_ENABLED": "1",
            }),
            patch("core.routing.routing_comprehension.default_judge", return_value=FakeJudge()),
        ):
            brain_loop.run_brain_loop(
                "I feel anxious about Nvidia stock today; check the latest price",
                action_engine=object(),
                get_pipeline=lambda: None,
                surface="telegram_surface",
                chat_id="chat",
            )

        self.assertEqual(seen["external_sources"], ["WEB_SEARCH"])
```

- [ ] **Step 2: Run tests to verify fail**

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_brain_loop.RoutingComprehensionShadow -v
```

Expected: first new test FAILS because enabled mode still does not mutate `spec`.

- [ ] **Step 3: Implement enabled spec mutation**

In the seam block from Task 2, after `_routing_comprehension_decision` is assigned, update:

```python
            _routing_comprehension_veto_applied = False
            if (
                _routing_comprehension.enabled()
                and _routing_comprehension_decision.vetoes_web_search
            ):
                _new_spec = _routing_comprehension.apply_web_search_veto(
                    spec,
                    _routing_comprehension_decision,
                )
                _routing_comprehension_veto_applied = _new_spec is not spec
                spec = _new_spec
            _routing_comprehension_receipt = _routing_comprehension.shadow_receipt(
                surface=surface,
                chat_id=chat_id,
                decision=_routing_comprehension_decision,
                trigger=_routing_comprehension_trigger,
                enabled=_routing_comprehension.enabled(),
                veto_applied=_routing_comprehension_veto_applied,
            )
```

Also initialize `_routing_comprehension_veto_applied = False` before the `try`.

- [ ] **Step 4: Run tests**

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_brain_loop.RoutingComprehensionShadow tests.test_routing_comprehension -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/brain/brain_loop.py tests/test_brain_loop.py
git commit -m "feat(routing): veto confident personal web-search misroutes"
```

---

### Task 4: Provenance Receipt Rail for Thread Follow-Ups

**Files:**
- Modify: `core/routing/attribution_render.py`
- Modify: `daemon/maez_daemon.py`
- Modify: `core/brain/brain_loop.py`
- Modify: `tests/test_attribution_render.py`
- Modify: `tests/test_brain_loop.py`

- [ ] **Step 1: Write failing receipt-store tests**

Append to `tests/test_attribution_render.py`:

```python
    def test_retain_receipt_keeps_optional_observation_metadata(self):
        from core.routing import attribution_render as ar

        ar.retain_receipt(
            "receipt-meta-chat",
            marked="Answer [E1]",
            sources=["https://source.test/a"],
            observation={
                "query": "Pretty nice. I did legs today.",
                "diagnostic_id": "diag-1",
                "kind": "web_search",
            },
        )
        receipt = ar.last_receipt("receipt-meta-chat")
        self.assertEqual(receipt["observation"]["query"], "Pretty nice. I did legs today.")
        self.assertEqual(receipt["sources"], ["https://source.test/a"])

    def test_last_web_receipt_context_returns_none_without_web_observation(self):
        from core.routing import attribution_render as ar

        self.assertIsNone(ar.last_web_receipt_context("no-such-chat"))

    def test_last_web_receipt_context_shapes_prior_tool_receipt(self):
        from core.routing import attribution_render as ar

        ar.retain_receipt(
            "receipt-context-chat",
            marked="Answer [E1]",
            sources=["https://source.test/a"],
            observation={
                "query": "What is happening with OpenAI?",
                "diagnostic_id": "diag-2",
            },
        )
        got = ar.last_web_receipt_context("receipt-context-chat")
        self.assertEqual(got.kind, "web_search")
        self.assertEqual(got.query, "What is happening with OpenAI?")
        self.assertEqual(got.sources, ("https://source.test/a",))
        self.assertEqual(got.diagnostic_id, "diag-2")
```

- [ ] **Step 2: Run receipt tests to verify fail**

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_attribution_render -v
```

Expected: FAIL because `retain_receipt` has no `observation` kwarg and no `last_web_receipt_context`.

- [ ] **Step 3: Extend receipt store compatibly**

Modify `core/routing/attribution_render.py`:

```python
def retain_receipt(chat_id: str, *, marked: str, sources: list[str], observation=None) -> None:
    try:
        key = str(chat_id)
        _RECEIPTS[key] = {
            "marked": marked,
            "sources": list(sources or []),
            "observation": dict(observation or {}) if isinstance(observation, dict) else None,
        }
        _RECEIPTS.move_to_end(key)
        while len(_RECEIPTS) > _MAX_RECEIPTS:
            _RECEIPTS.popitem(last=False)
    except Exception:
        pass


def last_web_receipt_context(chat_id: str):
    try:
        receipt = last_receipt(chat_id)
        if not receipt:
            return None
        observation = receipt.get("observation") or {}
        query = observation.get("query")
        diagnostic_id = observation.get("diagnostic_id")
        if not query and not diagnostic_id:
            return None
        from core.routing.routing_comprehension import PriorToolReceipt

        return PriorToolReceipt(
            kind=str(observation.get("kind") or "web_search"),
            query=str(query or ""),
            sources=tuple(str(item) for item in (receipt.get("sources") or ())[:5]),
            diagnostic_id=str(diagnostic_id or ""),
        )
    except Exception:
        return None
```

Existing `receipts_reply` should not change except it will ignore the new key.

- [ ] **Step 4: Thread observation metadata in daemon**

In `daemon/maez_daemon.py`, find:

```python
                retain_receipt(
                    chat_id,
                    marked=reply,
                    sources=list(_turn_ev.get("sources") or []),
                )
```

Replace with:

```python
                retain_receipt(
                    chat_id,
                    marked=reply,
                    sources=list(_turn_ev.get("sources") or []),
                    observation=_turn_ev.get("observation"),
                )
```

- [ ] **Step 5: Add failing thread-followup seam tests**

Append to `RoutingComprehensionShadow` in `tests/test_brain_loop.py`:

```python
    def test_thread_followup_veto_appends_prior_receipt_context(self):
        from core import brain_loop
        from core.routing import routing_comprehension as rc

        seen = {}
        spec = self._web_spec()

        class FakeJudge:
            def decide(self, context):
                seen["prior_receipt"] = context.prior_receipt
                return rc.JudgeDecision(
                    decision=rc.Decision.THREAD_FOLLOWUP_ANSWERABLE,
                    confidence=0.96,
                    reason_code="asks_about_prior_tool_use",
                )

        with self._patched_dispatcher(brain_loop, spec, seen), (
            patch.dict(os.environ, {
                "MAEZ_RECALL_TRIAD_ENABLED": "1",
                "MAEZ_ROUTING_COMPREHENSION_ENABLED": "1",
            }),
            patch("core.routing.routing_comprehension.default_judge", return_value=FakeJudge()),
            patch(
                "core.routing.attribution_render.last_web_receipt_context",
                return_value=rc.PriorToolReceipt(
                    kind="web_search",
                    query="Pretty nice. I did legs today.",
                    sources=("https://source.test/a",),
                    diagnostic_id="diag-3",
                ),
            ),
        ):
            result = brain_loop.run_brain_loop(
                "What did you check online for that?",
                action_engine=object(),
                get_pipeline=lambda: None,
                surface="telegram_surface",
                chat_id="chat",
            )

        self.assertEqual(seen["external_sources"], [])
        self.assertIn("PRIOR TOOL RECEIPT", result)
        self.assertIn("Pretty nice. I did legs today.", result)
        self.assertEqual(seen["prior_receipt"].diagnostic_id, "diag-3")

    def test_thread_followup_no_receipt_gets_honest_context_not_search(self):
        from core import brain_loop
        from core.routing import routing_comprehension as rc

        seen = {}
        spec = self._web_spec()

        class FakeJudge:
            def decide(self, context):
                return rc.JudgeDecision(
                    decision=rc.Decision.THREAD_FOLLOWUP_ANSWERABLE,
                    confidence=0.96,
                    reason_code="asks_about_prior_tool_use",
                )

        with self._patched_dispatcher(brain_loop, spec, seen), (
            patch.dict(os.environ, {
                "MAEZ_RECALL_TRIAD_ENABLED": "1",
                "MAEZ_ROUTING_COMPREHENSION_ENABLED": "1",
            }),
            patch("core.routing.routing_comprehension.default_judge", return_value=FakeJudge()),
            patch("core.routing.attribution_render.last_web_receipt_context", return_value=None),
        ):
            result = brain_loop.run_brain_loop(
                "What did you check online for that?",
                action_engine=object(),
                get_pipeline=lambda: None,
                surface="telegram_surface",
                chat_id="chat",
            )

        self.assertEqual(seen["external_sources"], [])
        self.assertIn("no retained web-search receipt", result)
```

- [ ] **Step 6: Run tests to verify fail**

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_attribution_render tests.test_brain_loop.RoutingComprehensionShadow -v
```

Expected: receipt tests pass after Steps 3–4; thread-followup tests FAIL until brain_loop threads prior receipt context.

- [ ] **Step 7: Thread receipt into judge context and transcript**

In `core/brain/brain_loop.py`, in the comprehension seam before constructing `JudgeContext`, add:

```python
            try:
                from core.routing.attribution_render import (
                    last_web_receipt_context as _last_web_receipt_context,
                )
                _routing_comprehension_prior_receipt = _last_web_receipt_context(chat_id)
            except Exception:
                _routing_comprehension_prior_receipt = None
```

Set `prior_receipt=_routing_comprehension_prior_receipt` in `JudgeContext`.

Initialize before fanout:

```python
    _routing_comprehension_context_block = ""
```

After enabled veto applies, add:

```python
            if (
                _routing_comprehension.enabled()
                and _routing_comprehension_decision.decision
                == _routing_comprehension.Decision.THREAD_FOLLOWUP_ANSWERABLE
                and _routing_comprehension_veto_applied
            ):
                _routing_comprehension_context_block = (
                    _routing_comprehension.receipt_context_text(
                        _routing_comprehension_prior_receipt
                    )
                )
```

After the `merge_fanout_results` call assigns `rendered_turn`, before returning, add:

```python
    _prompt_block = rendered_turn.prompt_block
    if _routing_comprehension_context_block:
        _prompt_block = f"{_prompt_block}\n\n{_routing_comprehension_context_block}"
```

Then return:

```python
    return _DispatcherPathResult(
        transcript=_prompt_block,
        should_run_jarvis=False,
        recall_items=getattr(rendered_turn, "recall_items", ()),
    )
```

- [ ] **Step 8: Run tests**

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_attribution_render tests.test_brain_loop.RoutingComprehensionShadow tests.test_routing_comprehension -v
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add core/routing/attribution_render.py daemon/maez_daemon.py core/brain/brain_loop.py tests/test_attribution_render.py tests/test_brain_loop.py
git commit -m "feat(routing): answer tool followups from retained receipts"
```

---

### Task 5: Four Witness Cases + Regression Sweep + Handoff

**Files:**
- Modify: `tests/test_brain_loop.py`
- Create: `docs/handoffs/2026-06-23-routing-comprehension-v0-handoff.md`

- [ ] **Step 1: Add four make-or-break integration tests**

Append to `RoutingComprehensionShadow` in `tests/test_brain_loop.py`:

```python
    def test_witness_personal_vulnerable_turn_vetoes(self):
        from core import brain_loop
        from core.routing import routing_comprehension as rc

        seen = {}
        spec = self._web_spec()

        class FakeJudge:
            def decide(self, context):
                self.assertIn("insecure", context.current_turn)
                return rc.JudgeDecision(
                    decision=rc.Decision.PERSONAL_OR_RELATIONAL,
                    confidence=0.97,
                    reason_code="owner_sharing_personal_state",
                )

        with self._patched_dispatcher(brain_loop, spec, seen), (
            patch.dict(os.environ, {
                "MAEZ_RECALL_TRIAD_ENABLED": "1",
                "MAEZ_ROUTING_COMPREHENSION_ENABLED": "1",
            }),
            patch("core.routing.routing_comprehension.default_judge", return_value=FakeJudge()),
        ):
            brain_loop.run_brain_loop(
                "I did legs today, I'm insecure about my legs",
                action_engine=object(),
                get_pipeline=lambda: None,
                surface="telegram_surface",
                chat_id="chat",
            )

        self.assertEqual(seen["external_sources"], [])

    def test_witness_thread_followup_vetoes_and_uses_receipt(self):
        from core import brain_loop
        from core.routing import routing_comprehension as rc

        seen = {}
        spec = self._web_spec()

        class FakeJudge:
            def decide(self, context):
                return rc.JudgeDecision(
                    decision=rc.Decision.THREAD_FOLLOWUP_ANSWERABLE,
                    confidence=0.97,
                    reason_code="asks_about_prior_tool_use",
                )

        with self._patched_dispatcher(brain_loop, spec, seen), (
            patch.dict(os.environ, {
                "MAEZ_RECALL_TRIAD_ENABLED": "1",
                "MAEZ_ROUTING_COMPREHENSION_ENABLED": "1",
            }),
            patch("core.routing.routing_comprehension.default_judge", return_value=FakeJudge()),
            patch(
                "core.routing.attribution_render.last_web_receipt_context",
                return_value=rc.PriorToolReceipt(
                    kind="web_search",
                    query="I did legs today, I'm insecure about my legs",
                    sources=("https://source.test/a",),
                    diagnostic_id="diag-4",
                ),
            ),
        ):
            result = brain_loop.run_brain_loop(
                "What did you check online for that?",
                action_engine=object(),
                get_pipeline=lambda: None,
                surface="telegram_surface",
                chat_id="chat",
            )

        self.assertEqual(seen["external_sources"], [])
        self.assertIn("Prior query: I did legs today", result)

    def test_witness_latest_openai_still_searches(self):
        from core import brain_loop
        from core.routing import routing_comprehension as rc

        seen = {}
        spec = self._web_spec()

        class FakeJudge:
            def decide(self, context):
                return rc.JudgeDecision(
                    decision=rc.Decision.EXTERNAL_INFO_REQUESTED,
                    confidence=0.98,
                    reason_code="owner_requests_current_information",
                )

        with self._patched_dispatcher(brain_loop, spec, seen), (
            patch.dict(os.environ, {
                "MAEZ_RECALL_TRIAD_ENABLED": "1",
                "MAEZ_ROUTING_COMPREHENSION_ENABLED": "1",
            }),
            patch("core.routing.routing_comprehension.default_judge", return_value=FakeJudge()),
        ):
            brain_loop.run_brain_loop(
                "What's the latest on OpenAI today?",
                action_engine=object(),
                get_pipeline=lambda: None,
                surface="telegram_surface",
                chat_id="chat",
            )

        self.assertEqual(seen["external_sources"], ["WEB_SEARCH"])

    def test_witness_emotional_data_request_still_searches(self):
        from core import brain_loop
        from core.routing import routing_comprehension as rc

        seen = {}
        spec = self._web_spec()

        class FakeJudge:
            def decide(self, context):
                self.assertIn("anxious", context.current_turn)
                return rc.JudgeDecision(
                    decision=rc.Decision.EXTERNAL_INFO_REQUESTED,
                    confidence=0.98,
                    reason_code="owner_requests_current_price",
                )

        with self._patched_dispatcher(brain_loop, spec, seen), (
            patch.dict(os.environ, {
                "MAEZ_RECALL_TRIAD_ENABLED": "1",
                "MAEZ_ROUTING_COMPREHENSION_ENABLED": "1",
            }),
            patch("core.routing.routing_comprehension.default_judge", return_value=FakeJudge()),
        ):
            brain_loop.run_brain_loop(
                "I feel anxious about Nvidia stock today; check the latest price",
                action_engine=object(),
                get_pipeline=lambda: None,
                surface="telegram_surface",
                chat_id="chat",
            )

        self.assertEqual(seen["external_sources"], ["WEB_SEARCH"])
```

- [ ] **Step 2: Run targeted suite**

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest \
  tests.test_routing_comprehension \
  tests.test_brain_loop.RoutingComprehensionShadow \
  tests.test_attribution_render \
  tests.test_dispatcher_layer0 \
  tests.test_dispatcher_external_sources \
  -v
```

Expected: PASS.

- [ ] **Step 3: Run ruff and diff check**

```bash
cd /home/rohit/maez
ruff check core/routing/routing_comprehension.py core/brain/brain_loop.py core/routing/attribution_render.py daemon/maez_daemon.py tests/test_routing_comprehension.py tests/test_brain_loop.py tests/test_attribution_render.py
git diff --check
```

Expected: both clean.

- [ ] **Step 4: Write handoff**

Create `docs/handoffs/2026-06-23-routing-comprehension-v0-handoff.md`:

```markdown
# Routing Comprehension v0 Handoff

## Branch

- Branch: routing-comprehension-v0
- Status: STOPPED at review gate.

## What Landed

- Pure 4-way external-info eligibility judge.
- Dispatcher seam before `ExternalFanout.run`.
- Shadow receipt under `MAEZ_ROUTING_COMPREHENSION_SHADOW`.
- Enabled veto under `MAEZ_ROUTING_COMPREHENSION_ENABLED`.
- Retained receipt metadata for thread follow-ups.
- Thread follow-up context block from retained receipt, or honest no-receipt context.

## Covenant Anchors

1. Meaning bouncer, not keyword bouncer: structural test forbids regex/keyword intent matching in the judge.
2. High precision: ambiguous/external decisions let search run.
3. Web-search only in v0; other tools untouched.
4. Default-off byte-identical: no judge call and no spec mutation.
5. Shadow-first: shadow logs typed decision but still searches.
6. Provenance rail: thread follow-up answers from retained receipt when available.
7. No fabrication: no receipt produces an honest no-receipt context.

## Tests

Paste exact commands and results:

```text
.venv/bin/python -m unittest tests.test_routing_comprehension tests.test_brain_loop.RoutingComprehensionShadow tests.test_attribution_render -v
ruff check core/routing/routing_comprehension.py core/brain/brain_loop.py core/routing/attribution_render.py daemon/maez_daemon.py tests/test_routing_comprehension.py tests/test_brain_loop.py tests/test_attribution_render.py
git diff --check
```

## Owner Witness

After review PASS:

1. Merge.
2. Restart Maez.
3. Shadow: `MAEZ_ROUTING_COMPREHENSION_SHADOW=1`.
4. Run four probes:
   - `I did legs today, I'm insecure about my legs` -> receipt says personal_or_relational; search still runs in shadow.
   - `What did you check online for that?` after a search -> receipt says thread_followup_answerable; search still runs in shadow.
   - `What's the latest on OpenAI today?` -> external_info_requested.
   - `I feel anxious about Nvidia stock today; check the latest price` -> external_info_requested.
5. Enabled: `MAEZ_ROUTING_COMPREHENSION_ENABLED=1`.
6. Re-run probes:
   - first two no longer search;
   - last two still search.

## Predicted Effect

Personal/relational turns and thread follow-ups stop triggering web search; genuine external requests still search; follow-up answers use retained receipts rather than inventing or searching again.
```

- [ ] **Step 5: Commit tests and handoff**

```bash
git add tests/test_brain_loop.py docs/handoffs/2026-06-23-routing-comprehension-v0-handoff.md
git commit -m "test(routing): pin comprehension witness cases"
```

---

## Review Gate

Before merge, ask for:

- Codex code review: actual seam, tests, no default-on behavior, no hidden search suppression.
- Claude covenant review: zero keyword/regex intent matching in the judge, no fabrication in receipt rail, and witness case #4 still searches.

Do not restart Maez or flip flags until both lanes pass.
