# Agnostic Local Judge Registry v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the photo-contradiction judge bakeoff candidate set data-driven, local-only, and model-agnostic while fixing MiniCheck to public `lytang/*` repos.

**Architecture:** Replace the hardcoded adapter-class list with `CandidateSpec` records plus a `build_candidates()` factory. Keep model calls inside existing adapters, but parameterize repo/model fields from specs. Preserve the runner hard contract and add a registry invariant that chat judges are loopback-only.

**Tech Stack:** Python `unittest`, dataclasses, existing `scripts/photo_judge_bakeoff*.py` harness.

---

## Files

- Modify: `scripts/photo_judge_bakeoff_adapters.py`
  - Add `CandidateSpec`, `CANDIDATES`, `validate_local_chat_specs()`, and `build_candidates()`.
  - Parameterize HHEM/MiniCheck/NLI/Reranker adapters.
  - Fail fast when a downloaded-model artifact directory is absent, so a no-download
    runner smoke reports unavailable candidates without importing heavyweight model libraries.
  - Convert `ALL_ADAPTERS` into a compatibility alias for registry specs, not classes.
- Modify: `scripts/photo_judge_bakeoff.py`
  - Use `build_candidates()` when no adapters are injected.
- Modify: `tests/test_photo_judge_bakeoff.py`
  - Add registry/local-only tests.
  - Replace the old class-list registration test.
  - Update adapter parameterization tests.
- Create: `docs/handoffs/2026-06-08-codex-agnostic-local-judge-registry-v0-review.md`
  - Review handoff after implementation.

## Birth-Readiness Review Backlog

These were built before the six-role covenant review became explicit in this lane. They are not assumed bad; they are queued for a later final review near birth:

- Desktop perception / Lens v0 / ScreenCast curtain / active-window eye arc.
- Chat Photo Vision and photo-focused synthesis.
- Photo Honesty Receipt v0.
- Ledger Activation / Disabled-State Honesty v0.
- Photo-Contradiction Judge Bakeoff v0 and this registry refactor.

---

### Task 1: Registry Spec + Local-Only Invariant

**Files:**
- Modify: `tests/test_photo_judge_bakeoff.py`
- Modify: `scripts/photo_judge_bakeoff_adapters.py`

- [ ] **Step 1: Write failing registry tests**

Add this class near `ConcreteAdapters` in `tests/test_photo_judge_bakeoff.py`:

```python
class CandidateRegistry(unittest.TestCase):
    def test_registry_contains_expected_local_specs(self):
        from scripts.photo_judge_bakeoff_adapters import CANDIDATES
        names = {c.name for c in CANDIDATES}
        self.assertEqual(names, {
            "hhem",
            "minicheck-roberta",
            "minicheck-flan-t5",
            "minicheck-deberta",
            "thinkncheck",
            "nli",
            "reranker",
            "chatjudge-maez-judge",
        })

    def test_minicheck_specs_use_public_lytang_repos(self):
        from scripts.photo_judge_bakeoff_adapters import CANDIDATES
        minis = [c for c in CANDIDATES if c.kind == "minicheck"]
        self.assertEqual({m.repo_id for m in minis}, {
            "lytang/MiniCheck-RoBERTa-Large",
            "lytang/MiniCheck-Flan-T5-Large",
            "lytang/MiniCheck-DeBERTa-v3-Large",
        })
        self.assertFalse(any("bespokelabs" in (m.repo_id or "") for m in minis))

    def test_chatjudge_specs_are_loopback_only(self):
        from scripts.photo_judge_bakeoff_adapters import (
            CANDIDATES, validate_local_chat_specs)
        validate_local_chat_specs(CANDIDATES)
        chat_specs = [c for c in CANDIDATES if c.kind == "chatjudge"]
        self.assertTrue(chat_specs)
        self.assertTrue(all(c.base_url.startswith("http://127.0.0.1:")
                            or c.base_url.startswith("http://localhost:")
                            for c in chat_specs))

    def test_external_chatjudge_spec_is_rejected(self):
        from scripts.photo_judge_bakeoff_adapters import (
            CandidateSpec, validate_local_chat_specs)
        bad = CandidateSpec(
            name="external",
            kind="chatjudge",
            base_url="https://api.example.com/v1",
            expected_alias="judge",
        )
        with self.assertRaises(ValueError):
            validate_local_chat_specs([bad])
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
.venv/bin/python -B -m unittest \
  tests.test_photo_judge_bakeoff.CandidateRegistry
```

Expected: FAIL/ERROR because `CANDIDATES`, `CandidateSpec`, and `validate_local_chat_specs` do not exist yet.

- [ ] **Step 3: Implement registry specs**

In `scripts/photo_judge_bakeoff_adapters.py`, add after `THRESHOLD_GRID`:

```python
from dataclasses import dataclass, field
from urllib.parse import urlparse


@dataclass(frozen=True)
class CandidateSpec:
    name: str
    kind: str
    repo_id: str | None = None
    base_url: str | None = None
    expected_alias: str | None = None
    params: dict = field(default_factory=dict)
```

Then add after the adapter classes:

```python
CANDIDATES = (
    CandidateSpec(name="hhem", kind="hhem",
                  repo_id="vectara/hallucination_evaluation_model"),
    CandidateSpec(name="minicheck-roberta", kind="minicheck",
                  repo_id="lytang/MiniCheck-RoBERTa-Large",
                  params={"model_name": "roberta-large"}),
    CandidateSpec(name="minicheck-flan-t5", kind="minicheck",
                  repo_id="lytang/MiniCheck-Flan-T5-Large",
                  params={"model_name": "flan-t5-large"}),
    CandidateSpec(name="minicheck-deberta", kind="minicheck",
                  repo_id="lytang/MiniCheck-DeBERTa-v3-Large",
                  params={"model_name": "deberta-v3-large"}),
    CandidateSpec(name="thinkncheck", kind="thinkncheck",
                  repo_id="thinkncheck/thinkncheck-1b-gemma3-q4"),
    CandidateSpec(name="nli", kind="nli",
                  repo_id="MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"),
    CandidateSpec(name="reranker", kind="reranker",
                  repo_id="Qwen/Qwen3-Reranker-0.6B"),
    CandidateSpec(name="chatjudge-maez-judge", kind="chatjudge",
                  base_url="http://127.0.0.1:8081",
                  expected_alias="maez-judge"),
)


def validate_local_chat_specs(specs=CANDIDATES):
    for spec in specs:
        if spec.kind != "chatjudge":
            continue
        parsed = urlparse(spec.base_url or "")
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
            raise ValueError(f"chatjudge spec {spec.name!r} must use loopback http")
```

Keep old `ALL_ADAPTERS` temporarily until Task 3 replaces it.

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```bash
.venv/bin/python -B -m unittest \
  tests.test_photo_judge_bakeoff.CandidateRegistry
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add scripts/photo_judge_bakeoff_adapters.py tests/test_photo_judge_bakeoff.py
git commit -m "feat(judge-registry): add local candidate specs"
```

---

### Task 2: Parameterize Existing Adapters

**Files:**
- Modify: `tests/test_photo_judge_bakeoff.py`
- Modify: `scripts/photo_judge_bakeoff_adapters.py`

- [ ] **Step 1: Write failing parameterization tests**

Update `ConcreteAdapters.test_all_adapters_registered` to test classes separately from specs, or remove it after Task 1 coverage. Add:

```python
    def test_minicheck_adapter_honors_repo_and_model_name(self):
        from scripts.photo_judge_bakeoff_adapters import MiniCheckAdapter
        with mock.patch.object(MiniCheckAdapter, "_load", return_value=object()):
            a = MiniCheckAdapter(
                name="minicheck-flan-t5",
                repo_id="lytang/MiniCheck-Flan-T5-Large",
                model_name="flan-t5-large",
            )
        self.assertEqual(a.name, "minicheck-flan-t5")
        self.assertEqual(a.model_id, "lytang/MiniCheck-Flan-T5-Large")
        self.assertEqual(a.model_name, "flan-t5-large")

    def test_repo_parameter_sets_model_id_on_score_adapters(self):
        from scripts.photo_judge_bakeoff_adapters import HHEMAdapter, NLIAdapter
        with mock.patch.object(HHEMAdapter, "_load", return_value=object()):
            h = HHEMAdapter(name="hhem-alt", repo_id="vectara/custom")
        with mock.patch.object(NLIAdapter, "_load", return_value=object()):
            n = NLIAdapter(name="nli-alt", repo_id="owner/nli")
        self.assertEqual(h.name, "hhem-alt")
        self.assertEqual(h.model_id, "vectara/custom")
        self.assertEqual(n.name, "nli-alt")
        self.assertEqual(n.model_id, "owner/nli")
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
.venv/bin/python -B -m unittest \
  tests.test_photo_judge_bakeoff.ConcreteAdapters
```

Expected: FAIL because adapters do not accept these keyword arguments yet.

- [ ] **Step 3: Implement adapter constructors**

Add `__init__` methods before each adapter's `_load` as needed:

```python
class HHEMAdapter(CandidateAdapter):
    name = "hhem"
    score_based = True
    model_id = "vectara/hallucination_evaluation_model"

    def __init__(self, threshold=None, name=None, repo_id=None):
        if name:
            self.name = name
        if repo_id:
            self.model_id = repo_id
        super().__init__(threshold=threshold)
```

Repeat the same pattern for `NLIAdapter` and `RerankerAdapter`.

For `MiniCheckAdapter`:

```python
class MiniCheckAdapter(CandidateAdapter):
    name = "minicheck-roberta"
    score_based = False
    model_id = "lytang/MiniCheck-RoBERTa-Large"
    model_name = "roberta-large"

    def __init__(self, threshold=None, name=None, repo_id=None, model_name=None):
        if name:
            self.name = name
        if repo_id:
            self.model_id = repo_id
        if model_name:
            self.model_name = model_name
        super().__init__(threshold=threshold)

    def _load(self):
        from minicheck.minicheck import MiniCheck
        return MiniCheck(model_name=self.model_name,
                         cache_dir=os.path.join(_BAKEOFF_CACHE, self.name))
```

For `ThinknCheckAdapter`, add optional `name`/`repo_id` and use `self.name` in cache path.

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```bash
.venv/bin/python -B -m unittest \
  tests.test_photo_judge_bakeoff.ConcreteAdapters \
  tests.test_photo_judge_bakeoff.CandidateRegistry
```

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

```bash
git add scripts/photo_judge_bakeoff_adapters.py tests/test_photo_judge_bakeoff.py
git commit -m "refactor(judge-registry): parameterize bakeoff adapters"
```

---

### Task 3: Candidate Factory + Runner Default

**Files:**
- Modify: `tests/test_photo_judge_bakeoff.py`
- Modify: `scripts/photo_judge_bakeoff_adapters.py`
- Modify: `scripts/photo_judge_bakeoff.py`

- [ ] **Step 1: Write failing factory/runner tests**

Add:

```python
    def test_build_candidates_returns_one_adapter_per_spec(self):
        from scripts.photo_judge_bakeoff_adapters import (
            CANDIDATES, build_candidates)
        with mock.patch("scripts.photo_judge_bakeoff_adapters.HHEMAdapter._load",
                        return_value=object()), \
             mock.patch("scripts.photo_judge_bakeoff_adapters.MiniCheckAdapter._load",
                        return_value=object()), \
             mock.patch("scripts.photo_judge_bakeoff_adapters.ThinknCheckAdapter._load",
                        return_value=object()), \
             mock.patch("scripts.photo_judge_bakeoff_adapters.NLIAdapter._load",
                        return_value=object()), \
             mock.patch("scripts.photo_judge_bakeoff_adapters.RerankerAdapter._load",
                        return_value=object()), \
             mock.patch("scripts.photo_judge_bakeoff_adapters.ChatJudgeAdapter._list_models",
                        return_value=["maez-judge"]):
            adapters = build_candidates()
        self.assertEqual([a.name for a in adapters], [c.name for c in CANDIDATES])

    def test_default_runner_uses_registry_factory(self):
        import tempfile
        import scripts.photo_judge_bakeoff as r
        from scripts.photo_judge_bakeoff_adapters import CandidateAdapter

        class Fake(CandidateAdapter):
            name = "registry-fake"
            score_based = False
            model_id = "fake/local"
            def _load(self): return object()
            def _raw_predict(self, premise, hypothesis): return "grounded"

        outdir = tempfile.mkdtemp()
        with mock.patch("scripts.photo_judge_bakeoff_adapters.build_candidates",
                        return_value=[Fake(threshold=None)]) as factory:
            rc = r.main(["--label", "registry", "--out-dir", outdir,
                         "--corpus", str(CORPUS)])
        self.assertEqual(rc, 0)
        factory.assert_called_once()
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
.venv/bin/python -B -m unittest \
  tests.test_photo_judge_bakeoff.CandidateRegistry \
  tests.test_photo_judge_bakeoff.RunnerMain.test_default_runner_uses_registry_factory
```

Expected: FAIL because `build_candidates` does not exist and the runner still uses `ALL_ADAPTERS`.

- [ ] **Step 3: Implement factory and runner default**

In `scripts/photo_judge_bakeoff_adapters.py`, add:

```python
def build_candidates(specs=CANDIDATES):
    validate_local_chat_specs(specs)
    adapters = []
    for spec in specs:
        if spec.kind == "hhem":
            adapters.append(HHEMAdapter(name=spec.name, repo_id=spec.repo_id))
        elif spec.kind == "minicheck":
            adapters.append(MiniCheckAdapter(
                name=spec.name,
                repo_id=spec.repo_id,
                model_name=spec.params["model_name"],
            ))
        elif spec.kind == "thinkncheck":
            adapters.append(ThinknCheckAdapter(name=spec.name, repo_id=spec.repo_id))
        elif spec.kind == "nli":
            adapters.append(NLIAdapter(name=spec.name, repo_id=spec.repo_id))
        elif spec.kind == "reranker":
            adapters.append(RerankerAdapter(name=spec.name, repo_id=spec.repo_id))
        elif spec.kind == "chatjudge":
            adapters.append(ChatJudgeAdapter(
                name=spec.name,
                base_url=spec.base_url,
                expected_alias=spec.expected_alias or "maez-judge",
            ))
        else:
            raise ValueError(f"unknown candidate kind {spec.kind!r}")
    return adapters


ALL_ADAPTERS = CANDIDATES
```

Update `ChatJudgeAdapter.__init__` to accept `name=None` and set `self.name` before `super().__init__`.

In `scripts/photo_judge_bakeoff.py`:

```python
    if adapters is None:
        from scripts.photo_judge_bakeoff_adapters import build_candidates
        adapters = build_candidates()
```

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```bash
.venv/bin/python -B -m unittest tests.test_photo_judge_bakeoff
```

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

```bash
git add scripts/photo_judge_bakeoff.py scripts/photo_judge_bakeoff_adapters.py tests/test_photo_judge_bakeoff.py
git commit -m "feat(judge-registry): build bakeoff adapters from specs"
```

---

### Task 4: Regression Sweep + Handoff

**Files:**
- Create: `docs/handoffs/2026-06-08-codex-agnostic-local-judge-registry-v0-review.md`
- Modify: `docs/superpowers/specs/2026-06-08-agnostic-local-judge-registry-v0-design.md` only if implementation reveals a needed clarification.

- [ ] **Step 1: Run focused suite**

Run:

```bash
.venv/bin/python -B -m unittest tests.test_photo_judge_bakeoff
```

Expected: `OK`.

- [ ] **Step 2: Run default runner smoke**

Run a runner/build/report smoke without sending claims to a live local chat judge:

```bash
rm -rf /tmp/maez-photo-judge-registry-smoke
tmp=$(mktemp)
PYTHONPATH=/home/rohit/maez-wt-judge-registry \
  /home/rohit/maez/.venv/bin/python -B -m scripts.photo_judge_bakeoff \
  --label registry-smoke \
  --corpus "$tmp" \
  --out-dir /tmp/maez-photo-judge-registry-smoke
rm -f "$tmp"
```

Expected: exits 0 and reports unavailable candidates honestly. The real 14-case corpus
run is the owner-greenlit witness because a local chatjudge candidate may perform real
CPU judge calls.

- [ ] **Step 3: Run full floor**

Run:

```bash
.venv/bin/python -B -m unittest discover -s tests -p 'test_*.py'
```

Expected: ambient floor may contain known non-slice failures; compare with main if needed. Any failure in `tests.test_photo_judge_bakeoff` is a blocker.

- [ ] **Step 4: Write Codex handoff**

Create `docs/handoffs/2026-06-08-codex-agnostic-local-judge-registry-v0-review.md`:

```markdown
# Codex Handoff — Agnostic Local Judge Registry v0

Branch: `agnostic-local-judge-registry-v0`

## What Changed

- Replaced hardcoded bakeoff adapter classes with data-driven local candidate specs.
- Fixed MiniCheck to public `lytang/*` repos and added RoBERTa / Flan-T5 / DeBERTa variants.
- Kept the bakeoff local/open only. ChatJudge specs are loopback-only and still verify served aliases.
- Runner defaults to `build_candidates()` from the registry.

## Review Anchors

1. Registry is data, not hardcoded adapter classes.
2. MiniCheck uses only `lytang/*`, never `bespokelabs/*`.
3. ChatJudge specs cannot point outside loopback.
4. Runner still has no network/download/systemd/model.env behavior.
5. Report fingerprint behavior from Lane 2 remains intact.
6. Default runner honestly reports unavailable candidates instead of crashing.

## Verification

- `.venv/bin/python -B -m unittest tests.test_photo_judge_bakeoff`
- `.venv/bin/python -B scripts/photo_judge_bakeoff.py --label registry-smoke --out-dir /tmp/maez-photo-judge-registry-smoke`
- `.venv/bin/python -B -m unittest discover -s tests -p 'test_*.py'`
```

- [ ] **Step 5: Commit Task 4**

```bash
git add docs/handoffs/2026-06-08-codex-agnostic-local-judge-registry-v0-review.md
git commit -m "docs(judge-registry): hand off agnostic local registry for review"
```

---

## Final State

Do not merge. Report the branch tip, verification results, and the birth-readiness review backlog. The real model downloads + bakeoff witness remain a separate owner-greenlit step.
