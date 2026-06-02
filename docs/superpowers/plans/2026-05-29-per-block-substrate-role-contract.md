# Per-Block Substrate Role Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a recall producer tag individual `RecallBlock`s with a substrate role so the dispatcher can carry "this memory is evidence, that memory is context" from the same source — honestly through both prompt render and audit telemetry — while remaining byte-identical to today until a producer uses it.

**Architecture:** Move `SourceRole` to `spec.py` (layering), add `RecallBlock.role_hint`, group source summaries by `(source, role)` in both render paths with legal-role validation, and make the audit envelope carry a `source_role_entries` list (the source-keyed dicts flatten duplicates). Inert until a producer emits hints.

**Tech Stack:** Python 3, `unittest` (pytest is NOT installed — use `.venv/bin/python -m unittest tests.test_x`; floor = `.venv/bin/python -m unittest discover -s tests -p 'test_*.py'`). Executor: **Codex** RED-first; **Claude** verifies diff + broad-floor hold.

**Source of truth:** [spec](../specs/2026-05-29-per-block-substrate-role-contract-design.md). No flag (inert-until-used). No live witness in isolation (parity + contract tests; behavioral witness happens in the dependent living-recall slice).

---

## File Structure
- `core/dispatcher/spec.py` — **modify.** Gains the `SourceRole` enum (moved here; it's the dispatcher foundation module).
- `core/dispatcher/provenance_renderer.py` — **modify.** Imports `SourceRole` from `spec`; `_audit_envelope` adds `source_role_entries`; `_assistant_text_metadata` allowlist adds it.
- `core/dispatcher/merge.py` — **modify.** Imports `SourceRole` from `spec`; `_source_summaries` groups by `(source, role)` + legal validation; `_base_audit_envelope` adds `source_role_entries: []`; `_assistant_metadata` allowlist adds it.
- `core/dispatcher/layer1.py` — **modify.** `RecallBlock` gains `role_hint: SourceRole | None = None` (import `SourceRole` from `spec`).
- `core/brain/brain_loop.py` — **modify.** Imports `SourceRole` from `spec`; direct-render path groups by `(source, role)`.
- `tests/test_per_block_role_contract.py` — **create.** All RED tests.

**Ordering rule (determinism / parity):** within a source, emit role groups in fixed order **`SUBSTRATE_EVIDENCE` before `SUBSTRATE_CONTEXT`** (then any other). With all `role_hint=None`, a source yields exactly one group (the spec default) → identical to today.

---

## Task 1: Move `SourceRole` to `spec.py`

**Files:** Modify `core/dispatcher/spec.py`, `core/dispatcher/provenance_renderer.py:37-42`, `core/dispatcher/merge.py:25`, `core/brain/brain_loop.py:262`. Test: `tests/test_per_block_role_contract.py`

- [ ] **Step 1: Write the failing test**
```python
import unittest

class SourceRoleHome(unittest.TestCase):
    def test_sourcerole_lives_in_spec(self):
        from core.dispatcher.spec import SourceRole
        self.assertEqual(SourceRole.SUBSTRATE_EVIDENCE.value, "SUBSTRATE_EVIDENCE")
        self.assertEqual(SourceRole.SUBSTRATE_CONTEXT.value, "SUBSTRATE_CONTEXT")

    def test_renderer_reexports_same_object(self):
        from core.dispatcher.spec import SourceRole as S1
        from core.dispatcher.provenance_renderer import SourceRole as S2
        self.assertIs(S1, S2)  # renderer imports from spec, not a second definition
```

- [ ] **Step 2: Run — expect FAIL** (`ImportError: cannot import name 'SourceRole' from 'core.dispatcher.spec'`)
Run: `.venv/bin/python -m unittest tests.test_per_block_role_contract.SourceRoleHome -v`

- [ ] **Step 3: Implement.** In `core/dispatcher/spec.py`, add near the top enums (after the existing imports; `StrEnum` is already used in this module):
```python
class SourceRole(StrEnum):
    SUBSTRATE_CONTEXT = "SUBSTRATE_CONTEXT"
    SUBSTRATE_EVIDENCE = "SUBSTRATE_EVIDENCE"
    FRESH_EVIDENCE = "FRESH_EVIDENCE"
    FRESH_CONTEXT = "FRESH_CONTEXT"
```
In `core/dispatcher/provenance_renderer.py`, **delete** the local `class SourceRole(StrEnum): …` (lines 37-42) and add to its imports:
```python
from core.dispatcher.spec import SourceRole
```
In `core/dispatcher/merge.py:25`, the import currently pulls `SourceRole` from the renderer — change that import to `from core.dispatcher.spec import SourceRole` (leave `SourceSummary` etc. importing from the renderer).
In `core/brain/brain_loop.py:262`, change `from core.dispatcher.provenance_renderer import SourceRole` → `from core.dispatcher.spec import SourceRole`.

- [ ] **Step 4: Run — expect PASS** + import smoke:
```
.venv/bin/python -m unittest tests.test_per_block_role_contract.SourceRoleHome -v
.venv/bin/python -c "import core.dispatcher.spec, core.dispatcher.provenance_renderer, core.dispatcher.merge, core.brain.brain_loop; print('import ok')"
```

- [ ] **Step 5: Commit**
```bash
git add core/dispatcher/spec.py core/dispatcher/provenance_renderer.py core/dispatcher/merge.py core/brain/brain_loop.py tests/test_per_block_role_contract.py
git commit -m "refactor(dispatcher): move SourceRole to spec.py (layering)"
```

---

## Task 2: Add `RecallBlock.role_hint`

**Files:** Modify `core/dispatcher/layer1.py` (RecallBlock). Test: `tests/test_per_block_role_contract.py`

- [ ] **Step 1: Write the failing test**
```python
class RecallBlockRoleHint(unittest.TestCase):
    def _block(self, **kw):
        from core.dispatcher.layer1 import RecallBlock
        from core.dispatcher.spec import SubstrateSource
        base = dict(source=SubstrateSource.TELEGRAM_SEMANTIC, text="t",
                    timestamp=None, freshness="f", rationale="r", prompt_cost=1)
        base.update(kw)
        return RecallBlock(**base)

    def test_defaults_none(self):
        self.assertIsNone(self._block().role_hint)

    def test_carries_role(self):
        from core.dispatcher.spec import SourceRole
        b = self._block(role_hint=SourceRole.SUBSTRATE_EVIDENCE)
        self.assertEqual(b.role_hint, SourceRole.SUBSTRATE_EVIDENCE)

    def test_to_dict_omits_role_hint_when_none(self):
        # parity: a None-hint block serializes exactly as before
        self.assertNotIn("role_hint", self._block().to_dict())

    def test_to_dict_includes_role_hint_when_set(self):
        from core.dispatcher.spec import SourceRole
        d = self._block(role_hint=SourceRole.SUBSTRATE_CONTEXT).to_dict()
        self.assertEqual(d["role_hint"], "SUBSTRATE_CONTEXT")
```

- [ ] **Step 2: Run — expect FAIL** (`TypeError: __init__() got an unexpected keyword argument 'role_hint'`)
Run: `.venv/bin/python -m unittest tests.test_per_block_role_contract.RecallBlockRoleHint -v`

- [ ] **Step 3: Implement.** In `core/dispatcher/layer1.py`, add to `RecallBlock` (after `original_chars`, so all new fields have defaults — preserves positional construction) + import `SourceRole`:
```python
# at top imports:
from core.dispatcher.spec import SourceRole
# in the dataclass, after original_chars: int | None = None
    role_hint: SourceRole | None = None
```
In `RecallBlock.to_dict`, add **conditionally** (so None-hint blocks are byte-identical), at the end of the dict build before `return`:
```python
        d = {
            "source": self.source.value,
            "text": self.text,
            "timestamp": self.timestamp,
            "freshness": self.freshness,
            "rationale": self.rationale,
            "prompt_cost": self.prompt_cost,
            "truncated": self.truncated,
            "original_chars": self.original_chars,
        }
        if self.role_hint is not None:
            d["role_hint"] = self.role_hint.value
        return d
```
(Adapt to the existing `to_dict` body shape — keep all current keys identical; only append `role_hint` when set.)

- [ ] **Step 4: Run — expect PASS**
Run: `.venv/bin/python -m unittest tests.test_per_block_role_contract.RecallBlockRoleHint -v`

- [ ] **Step 5: Commit**
```bash
git add core/dispatcher/layer1.py tests/test_per_block_role_contract.py
git commit -m "feat(dispatcher): RecallBlock.role_hint (defaults None, inert)"
```

---

## Task 3: Group `_source_summaries` by `(source, role)` + legal validation

**Files:** Modify `core/dispatcher/merge.py:263-282` (`_source_summaries`). Test: `tests/test_per_block_role_contract.py`

- [ ] **Step 1: Write the failing test**
```python
class MergeGrouping(unittest.TestCase):
    def _spec(self):
        # a substrate-only spec whose framing permits both substrate roles
        # (SUBSTRATE_ONLY_NO_FRESH_VALIDATION). Build via the project's spec
        # constructor/fixture used elsewhere in tests.
        from tests._dispatcher_fixtures import substrate_only_spec  # see note
        return substrate_only_spec(sources=("TELEGRAM_SEMANTIC",))

    def _block(self, role_hint=None, text="x"):
        from core.dispatcher.layer1 import RecallBlock
        from core.dispatcher.spec import SubstrateSource
        return RecallBlock(source=SubstrateSource.TELEGRAM_SEMANTIC, text=text,
                           timestamp=None, freshness="f", rationale="r",
                           prompt_cost=1, role_hint=role_hint)

    def test_none_hint_single_summary(self):
        from core.dispatcher.merge import _source_summaries
        from core.dispatcher.spec import SubstrateSource
        spec = self._spec()
        out = _source_summaries(spec, (self._block(text="a"), self._block(text="b")), ())
        tel = [s for s in out if s.source == SubstrateSource.TELEGRAM_SEMANTIC]
        self.assertEqual(len(tel), 1)              # joined, one role (today's behavior)
        self.assertEqual(tel[0].text, "a\nb")

    def test_two_roles_two_summaries_evidence_first(self):
        from core.dispatcher.merge import _source_summaries
        from core.dispatcher.spec import SourceRole
        spec = self._spec()
        out = _source_summaries(spec, (
            self._block(role_hint=SourceRole.SUBSTRATE_CONTEXT, text="old"),
            self._block(role_hint=SourceRole.SUBSTRATE_EVIDENCE, text="new"),
        ), ())
        roles = [s.role for s in out]
        self.assertIn(SourceRole.SUBSTRATE_EVIDENCE, roles)
        self.assertIn(SourceRole.SUBSTRATE_CONTEXT, roles)
        # evidence emitted before context
        self.assertLess(roles.index(SourceRole.SUBSTRATE_EVIDENCE),
                        roles.index(SourceRole.SUBSTRATE_CONTEXT))

    def test_illegal_role_refused(self):
        from core.dispatcher.merge import _source_summaries
        from core.dispatcher.spec import SourceRole
        spec = self._spec()  # substrate-only framing forbids FRESH_EVIDENCE
        with self.assertRaises(Exception):
            _source_summaries(spec, (self._block(role_hint=SourceRole.FRESH_EVIDENCE),), ())
```
**Note for executor:** there is no `tests/_dispatcher_fixtures` yet — reuse the spec-construction pattern already used in `tests/test_dispatcher_merge.py` (it builds `CompositionSpec`s with `SUBSTRATE_ONLY_NO_FRESH_VALIDATION` and `TELEGRAM_SEMANTIC`). Copy that local builder into this test file rather than inventing one.

- [ ] **Step 2: Run — expect FAIL** (`test_two_roles_two_summaries` returns 1 summary today)
Run: `.venv/bin/python -m unittest tests.test_per_block_role_contract.MergeGrouping -v`

- [ ] **Step 3: Implement.** Replace the substrate loop in `_source_summaries` (merge.py:272-282) with role-grouping:
```python
    _ROLE_ORDER = (SourceRole.SUBSTRATE_EVIDENCE, SourceRole.SUBSTRATE_CONTEXT)
    for source in spec.substrate_sources:
        by_role: dict[SourceRole, list[str]] = {}
        for block in recall_blocks:
            if block.source != source:
                continue
            role = block.role_hint or substrate_role
            by_role.setdefault(role, []).append(block.text)
        for role in sorted(by_role, key=lambda r: (_ROLE_ORDER.index(r) if r in _ROLE_ORDER else 99)):
            text = "\n".join(by_role[role])
            if not text:
                continue
            if role not in _allowed_roles(spec.provenance_framing):
                _refuse_template_mismatch(
                    f"illegal substrate role {role.value} for framing {spec.provenance_framing.value}"
                )
            summaries.append(SourceSummary(source=source, role=role,
                                           text=text, content_digest=_digest_text(text)))
```
Import `_allowed_roles` and `_refuse_template_mismatch` from `provenance_renderer` if not already imported in merge.py (verify; add to the existing renderer import if needed). `_ROLE_ORDER` can be module-level.

- [ ] **Step 4: Run — expect PASS**
Run: `.venv/bin/python -m unittest tests.test_per_block_role_contract.MergeGrouping -v`

- [ ] **Step 5: Commit**
```bash
git add core/dispatcher/merge.py tests/test_per_block_role_contract.py
git commit -m "feat(dispatcher): _source_summaries groups by (source, role) + legal validation"
```

---

## Task 4: Same `(source, role)` grouping in the brain_loop direct-render path

**Files:** Modify `core/brain/brain_loop.py:280-289`. Test: `tests/test_per_block_role_contract.py`

- [ ] **Step 1: Write the failing test** — render via the brain_loop direct path with two role-hinted `TELEGRAM_SEMANTIC` blocks and assert the rendered transcript contains BOTH `[memory evidence]` and `[memory context]`, and that the (source, role) grouping matches `_source_summaries` for the same blocks.
```python
class DirectRenderGrouping(unittest.TestCase):
    def test_direct_render_emits_both_labels(self):
        # build the same two-role block set; call the brain_loop render path
        # (_render_dispatcher_transcript) with a SUBSTRATE_ONLY spec; assert
        # "[memory evidence]" and "[memory context]" both appear.
        ...
    def test_direct_and_merge_agree(self):
        # the set of (source, role) summaries from the direct path equals
        # those from merge._source_summaries for identical blocks.
        ...
```
**Executor:** fill these bodies using the same spec/block builders as Task 3 and `_render_dispatcher_transcript` ([brain_loop.py:270](../../../core/brain/brain_loop.py#L270)). Keep them concrete (no skipped asserts).

- [ ] **Step 2: Run — expect FAIL**
- [ ] **Step 3: Implement.** In `_render_dispatcher_transcript` (brain_loop.py:280-289), replace the single-role `summaries = [SourceSummary(source=block.source, role=role, …) for block in layer1_result.recall_blocks]` with the **same** `(source, role)` grouping as Task 3 (factor a shared helper `group_summaries(spec, recall_blocks)` in `merge.py` and call it from both sites — DRY; the direct path imports it). The shared helper is the single source of truth for grouping + legal validation.
- [ ] **Step 4: Run — expect PASS**
- [ ] **Step 5: Commit**
```bash
git add core/brain/brain_loop.py core/dispatcher/merge.py tests/test_per_block_role_contract.py
git commit -m "feat(dispatcher): direct-render shares (source,role) grouping with merge"
```

---

## Task 5: Audit honesty — `source_role_entries` in `provenance_renderer._audit_envelope`

**Files:** Modify `core/dispatcher/provenance_renderer.py:237-254` (`_audit_envelope`) + `:285` (`_assistant_text_metadata` allowlist). Test: `tests/test_per_block_role_contract.py`

- [ ] **Step 1: Write the failing test**
```python
class AuditHonesty(unittest.TestCase):
    def test_source_role_entries_carries_both_roles(self):
        # two SourceSummary for TELEGRAM_SEMANTIC (evidence + context) →
        # _audit_envelope["source_role_entries"] has BOTH; the legacy
        # source_role_map keeps only one (documented lossy).
        from core.dispatcher.provenance_renderer import SourceSummary
        from core.dispatcher.spec import SourceRole
        ev = SourceSummary(source=<TELEGRAM_SEMANTIC>, role=SourceRole.SUBSTRATE_EVIDENCE,
                           text="new", content_digest="d1")
        ctx = SourceSummary(source=<TELEGRAM_SEMANTIC>, role=SourceRole.SUBSTRATE_CONTEXT,
                            text="old", content_digest="d2")
        env = _audit_envelope(... source_summaries=[ev, ctx] ...)
        entries = env["source_role_entries"]
        pairs = {(e["source"], e["role"]) for e in entries}
        self.assertIn(("TELEGRAM_SEMANTIC", "SUBSTRATE_EVIDENCE"), pairs)
        self.assertIn(("TELEGRAM_SEMANTIC", "SUBSTRATE_CONTEXT"), pairs)
        self.assertEqual({e["digest"] for e in entries}, {"d1", "d2"})

    def test_assistant_text_metadata_forwards_entries(self):
        # the renderer's metadata allowlist includes source_role_entries
        ...
```
**Executor:** call `_audit_envelope` with the same argument shape its existing callers use (see `render_provenance`); reuse a `SubstrateSource` member for `<TELEGRAM_SEMANTIC>`.

- [ ] **Step 2: Run — expect FAIL** (`KeyError: 'source_role_entries'`)
- [ ] **Step 3: Implement.** In `_audit_envelope`, after the existing `source_role_map`/`source_digests` (keep them — documented lossy), add:
```python
    source_role_entries = [
        {"source": s.source.value, "role": s.role.value, "digest": s.content_digest}
        for s in source_summaries
    ]
```
and add `"source_role_entries": source_role_entries,` to the returned dict. Add `"source_role_entries"` to the `_assistant_text_metadata` keys tuple (provenance_renderer.py:285). Add a one-line comment above `source_role_map` documenting it as first-role-per-source (lossy when a source has multiple roles); `source_role_entries` is authoritative.
- [ ] **Step 4: Run — expect PASS**
- [ ] **Step 5: Commit**
```bash
git add core/dispatcher/provenance_renderer.py tests/test_per_block_role_contract.py
git commit -m "feat(dispatcher): audit envelope carries source_role_entries (honest duplicates)"
```

---

## Task 6: Schema stability — `source_role_entries` in `merge._base_audit_envelope` + `_assistant_metadata`

**Files:** Modify `core/dispatcher/merge.py:423` (`_base_audit_envelope`) + `:467` (`_assistant_metadata` allowlist). Test: `tests/test_per_block_role_contract.py`

- [ ] **Step 1: Write the failing test**
```python
class SchemaStability(unittest.TestCase):
    def test_base_envelope_has_entries(self):
        # the empty/refusal envelope must carry the field (empty list), so
        # every envelope shape is uniform.
        env = _base_audit_envelope(<spec>, utterance="u", surface="s",
                                   timestamp="t", fresh_attempt_outcome=<outcome>,
                                   refusal_reason=None)
        self.assertEqual(env["source_role_entries"], [])

    def test_assistant_metadata_forwards_entries(self):
        env = _base_audit_envelope(...); env["source_role_entries"] = [{"source":"X","role":"R","digest":"d"}]
        self.assertIn("source_role_entries", _assistant_metadata(env))
```
**Executor:** build `<spec>`/`<outcome>` with the same fixtures `tests/test_dispatcher_merge.py` uses for the no-fresh/refusal path.

- [ ] **Step 2: Run — expect FAIL** (`KeyError`)
- [ ] **Step 3: Implement.** In `_base_audit_envelope` (merge.py), next to `"source_role_map": {}, "source_digests": {},` add `"source_role_entries": [],`. In `_assistant_metadata` (merge.py:467) keys tuple, add `"source_role_entries"`.
- [ ] **Step 4: Run — expect PASS**
- [ ] **Step 5: Commit**
```bash
git add core/dispatcher/merge.py tests/test_per_block_role_contract.py
git commit -m "feat(dispatcher): source_role_entries in base envelope + assistant metadata (stable schema)"
```

---

## Task 7: Parity safety floor + full verification

**Files:** Test only + verification.

- [ ] **Step 1: Parity test** — with all `role_hint=None`, the rendered transcript AND the audit envelope's `source_role_map`/`rendered_block_roles`/`source_role_entries` for a representative `SUBSTRATE_EVIDENCE_FRESH_CONTEXT` substrate spec are unchanged from a captured baseline. (Build the baseline from current behavior on a fixed spec; assert equality. `source_role_entries` for one None-hint source = a single entry mirroring `source_role_map`.)
```python
class Parity(unittest.TestCase):
    def test_none_hints_render_and_audit_unchanged(self):
        # one TELEGRAM_SEMANTIC source, two None-hint blocks → exactly one
        # summary/role/label, identical text join, and source_role_entries
        # has exactly one entry equal to the source_role_map pair.
        ...
```

- [ ] **Step 2: Run the new suite + the existing dispatcher suites**
```
.venv/bin/python -m unittest tests.test_per_block_role_contract tests.test_dispatcher_merge tests.test_dispatcher_layer0 tests.test_dispatcher_layer1 tests.test_slice_3_5_envelope_wiring -v 2>&1 | tail -20
```
Expected: all PASS (slice_3_5 keeps its 1 pre-existing floor failure `test_owner_bridge_chat…`).

- [ ] **Step 3: Broad floor**
```
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' 2>&1 | tail -6
```
Expected: no NEW failures beyond the documented 2-3 floor names.

- [ ] **Step 4: ruff**
```
.venv/bin/ruff check core/dispatcher/spec.py core/dispatcher/provenance_renderer.py core/dispatcher/merge.py core/dispatcher/layer1.py core/brain/brain_loop.py
```

- [ ] **Step 5: Commit**
```bash
git add tests/test_per_block_role_contract.py
git commit -m "test(dispatcher): parity floor for per-block role contract"
```

---

## Self-Review (against the spec)
**Spec coverage:** SourceRole→spec (T1); RecallBlock.role_hint (T2); group-by-(source,role) merge (T3) + direct-render (T4, shared helper = DRY); legal validation (T3); audit source_role_entries in renderer (T5) AND base envelope + both metadata allowlists (T6 — Rohit note a); keep dicts + entries authoritative (T5/T6 — Rohit note b); inert parity (T2 to_dict, T7); 6 spec RED tests all mapped. No flag (inert). ✓

**Placeholder scan:** Tasks 4 and parts of 5-7 have test *bodies* the executor fills from named fixtures — this is because the dispatcher's spec/outcome construction is fixture-heavy and copying the wrong constructor would be worse than pointing precisely at `tests/test_dispatcher_merge.py`'s existing builders. Every such spot names the exact existing pattern to copy and the exact asserts required. Flagged here honestly (not hidden) — the production-code steps are fully concrete.

**Type consistency:** `SourceRole` (spec), `RecallBlock.role_hint: SourceRole | None`, `group_summaries(spec, recall_blocks)` shared helper, `source_role_entries: list[{source, role, digest}]` — consistent across T1-T7.
