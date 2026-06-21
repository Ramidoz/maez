# Earned-Maturity Routing — Slice 3b (Beta-Binomial belief, shadow-compared) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the crude `n/8` confidence curve with a Beta-Binomial belief whose confidence *emerges* from how consistent the evidence is — but **only in shadow**: log old (`n/8`) and new (Beta) side by side, change NO behavior, and prove Beta is *better calibrated* (uncertain on thin/mixed where `n/8` overclaims) before any graduation flag is flipped.

**Architecture:** A pure `beta_belief` (one `scipy.stats.beta.cdf` call → `P(work_rate ≤ bad_threshold)`) + a `compare_beliefs(store)` that returns, per `(class, tool)`, the `n/8` verdict and the Beta verdict side by side. The daemon prior-consult seam logs the comparison behind `MAEZ_ROUTING_BETA_SHADOW` (no behavior change). A second default-off flag `MAEZ_ROUTING_BETA_ENABLED` swaps the veto's verdict from `n/8` to Beta — shipped but NOT flipped here; the owner flips it only after the calibration witness. The Beta prior + credence stay FIXED in 3b (3c makes them earned).

**Tech Stack:** Python 3, `scipy.stats.beta` (1.17.1, available; lazy-imported only when a Beta flag is on). Reuses Slice 1's `learn_priors` bucketing + `_confidence`/`_GOOD`. Tests: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.<module> -v` (named only).

**Lane:** TDD; branch via worktree `earned-maturity-slice3b`; STOP at review gate (owner-sovereign merge + restart). Claude two-stage + Codex cross-lane. `## Predicted effect` on behavior commits. GIT HYGIENE: NO checkout/switch/reset/rebase; verify "On branch earned-maturity-slice3b" after each commit; STOP if detached. main local-only, no push.

**Flags (both default-off = byte-identical to Slice 1's `n/8` veto):**
- `MAEZ_ROUTING_BETA_SHADOW` — compute + log the `n/8`-vs-Beta comparison per turn. NO behavior change.
- `MAEZ_ROUTING_BETA_ENABLED` — the veto uses Beta's verdict instead of `n/8`. Shipped default-off; flipped only AFTER the calibration witness shows Beta is saner.

**The five hard gates (owner — the graduation bar, enforced in Task 1 tests + Task 3 receipt):**
1. old `n/8` and new Beta logged side by side;
2. skeptical prior → thin evidence stays UNCERTAIN (no veto on a tiny streak);
3. NO behavior change until the comparison receipts show Beta better-calibrated (both flags off = byte-identical; ENABLED stays off through 3b);
4. the Barchart-class still vetoes under Beta — but that alone is NOT graduation;
5. on MIXED evidence Beta is *less* confident than `n/8` (abstains where `n/8` vetoes) — else the model isn't earning its keep.

---

## File Structure

- **`core/routing/observation/priors.py`** (modify): add `beta_belief(usable, n, ...)` (pure, scipy) + `compare_beliefs(store, ...)` returning `BeliefComparison` per `(class, tool)`. Leave `learn_priors`/`_confidence`/`RoutingPrior` UNCHANGED (the `n/8` path stays live).
- **`daemon/maez_daemon.py`** (modify, 2 small seams): at the prior-consult (~5912-5916) compute + log the comparison behind `MAEZ_ROUTING_BETA_SHADOW`; at the veto application, swap the verdict to Beta behind `MAEZ_ROUTING_BETA_ENABLED` (default-off).
- **Tests:** `tests/test_beta_belief.py` (the math + comparison + the five-gate calibration cases), `tests/test_beta_shadow_seam.py` (the daemon helper).
- **Docs:** `docs/proof/2026-06-20-slice3b-task0.md`, `docs/handoffs/2026-06-20-slice3b-handoff.md` (incl. the calibration table — the "provably saner" artifact).

---

### Task 0: Proof gate (seam + scipy + the verdict statistic) — docs/proof only

**Files:** Create `docs/proof/2026-06-20-slice3b-task0.md`.

- [ ] **Step 1: Seam (HARD).** Confirm the prior consult at [maez_daemon.py:5912-5916](../../daemon/maez_daemon.py#L5912) (`learn_priors(_default_store()).get((_cls, "web_search"))` + the `routing_prior_shadow` log) is where the comparison is computed/logged; `_cls`, `_default_store` in scope. Confirm the veto application below it (the `if PRIORS_ENABLED and _prior_vetoes_reflex(_prior) and _override_event_id is None: _reflex=False` line) is where `MAEZ_ROUTING_BETA_ENABLED` swaps the verdict. Record both line numbers.
- [ ] **Step 2: scipy (HARD).** Confirm `from scipy.stats import beta as _beta_dist; _beta_dist.cdf(0.4, 1, 6)` ≈ 0.953 (= `1 - 0.6**6`). Record that scipy is lazy-imported ONLY inside the flag-gated path (it is heavy; must not load when the flags are off).
- [ ] **Step 3: The verdict statistic.** Record: `beta_would_veto = P(work_rate ≤ max_success) ≥ credence`, where `P(...) = beta.cdf(max_success, prior_alpha + usable, prior_beta + (n - usable))`. Defaults: `prior_alpha=1.0, prior_beta=1.0` (uniform/skeptical), `max_success=0.4`, `credence=0.9`, `min_observations=3`. The `n/8` verdict mirrors Slice 1: `n8_would_veto = (_confidence(n) ≥ 0.6 and success_rate ≤ 0.4)` for `n ≥ 3`. Hand-verify the three calibration anchors (Step in Task 1) and record them.
- [ ] **Step 4: Scope.** Only `priors.py` + the 2 daemon seams + tests + docs. The `n/8` `learn_priors`/`_prior_vetoes_reflex` path stays LIVE (3b adds a parallel belief; off-flag the veto still uses `n/8`). Commit.

```bash
git add docs/proof/2026-06-20-slice3b-task0.md
git commit -m "docs(proof): slice3b Task 0 — Beta seam + scipy + verdict statistic confirmed"
```

**GO/NO-GO:** seam + scipy confirmed, else STOP.

---

### Task 1: The Beta belief + side-by-side comparison (pure; the five-gate calibration)

**Files:** Modify `core/routing/observation/priors.py`; Test `tests/test_beta_belief.py`.

- [ ] **Step 1: Write the failing test** — the math + the five-gate calibration (these ARE the graduation bar):

```python
import os, tempfile, unittest
os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test")
os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")
from core.routing.observation import RoutingObservationStore
from core.routing.observation.priors import beta_belief, compare_beliefs, BeliefComparison

class BetaBeliefTest(unittest.TestCase):
    def test_beta_belief_consistent_failures_confident(self):
        # 5 straight failures, uniform prior -> P(rate<=0.4) ~ 0.95 (= 1 - 0.6**6)
        mean, p_below = beta_belief(usable=0, n=5)
        self.assertAlmostEqual(p_below, 1 - 0.6**6, places=4)
        self.assertLess(mean, 0.2)

    def test_beta_belief_thin_stays_uncertain(self):   # GATE 2: thin -> uncertain
        _, p2 = beta_belief(usable=0, n=2)             # 1 - 0.6**3 = 0.784 < 0.9
        self.assertLess(p2, 0.9)

    def test_beta_belief_mixed_is_uncertain(self):     # GATE 5: mixed -> Beta unsure
        _, p = beta_belief(usable=2, n=5)              # Beta(3,4): P(rate<=0.4) < 0.5
        self.assertLess(p, 0.5)

class CompareBeliefsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.store = RoutingObservationStore(db_path=self.tmp.name)
    def tearDown(self):
        self.tmp.close()
        try: os.unlink(self.tmp.name)
        except OSError: pass
    def _rows(self, qualities):
        for q in qualities:
            self.store.record_legacy_web_search_observation(
                user_text="t", surface="cockpit", chat_id=None, chosen_tool="web_search",
                execution_status="success", evidence_block_count=2, outcome_quality=q,
                request_class_id="SIG", request_class_score=0.7, request_class_version="v0")

    def test_consistent_both_veto(self):               # GATE 4: Barchart-class still vetoes
        self._rows(["unusable"] * 5)
        c = compare_beliefs(self.store)[("SIG", "web_search")]
        self.assertTrue(c.n8_would_veto); self.assertTrue(c.beta_would_veto)

    def test_thin_both_abstain(self):                  # GATE 2
        self._rows(["unusable"] * 2)
        c = compare_beliefs(self.store)[("SIG", "web_search")]
        self.assertFalse(c.n8_would_veto); self.assertFalse(c.beta_would_veto)

    def test_mixed_n8_overclaims_beta_abstains(self):  # GATE 5 — the keystone divergence
        self._rows(["unusable", "unusable", "unusable", "structured_evidence", "structured_evidence"])
        c = compare_beliefs(self.store)[("SIG", "web_search")]
        self.assertTrue(c.n8_would_veto)               # n/8: n=5 conf 0.625, success_rate 0.4 -> vetoes
        self.assertFalse(c.beta_would_veto)            # Beta: Beta(3,4) stays uncertain -> abstains
        self.assertLess(c.beta_p_below, c.n8_confidence)  # Beta less confident than n/8 on mixed
```
Run; confirm FAIL (symbols missing).

- [ ] **Step 2: Implement in `priors.py`** (add below `learn_priors`; do NOT change existing code):

```python
from dataclasses import dataclass  # already imported at top; keep one import

def beta_belief(usable: int, n: int, *, prior_alpha: float = 1.0, prior_beta: float = 1.0,
                max_success: float = 0.4) -> tuple[float, float]:
    """Beta-Binomial belief about a (class,tool)'s USABLE-work-rate. Returns
    (posterior_mean, p_below) where p_below = P(work_rate <= max_success) under
    Beta(prior_alpha+usable, prior_beta+failures). Confidence EMERGES from consistency:
    a few mixed/thin observations stay near the prior (uncertain); only sustained
    consistency pushes p_below high. The prior is the 'how cautious' knob (3c earns it)."""
    from scipy.stats import beta as _beta_dist   # lazy: heavy; only when a Beta flag is on
    a = prior_alpha + usable
    b = prior_beta + (n - usable)
    mean = a / (a + b)
    p_below = float(_beta_dist.cdf(max_success, a, b))
    return mean, p_below

@dataclass(frozen=True)
class BeliefComparison:
    request_class: str
    chosen_tool: str
    n: int
    usable: int
    n8_confidence: float
    n8_success_rate: float
    n8_would_veto: bool
    beta_mean: float
    beta_p_below: float
    beta_would_veto: bool

def compare_beliefs(store, *, min_observations: int = 3, n8_min_conf: float = 0.6,
                    max_success: float = 0.4, credence: float = 0.9,
                    prior_alpha: float = 1.0, prior_beta: float = 1.0
                    ) -> dict[tuple[str, str], BeliefComparison]:
    """Per (class,tool): the old n/8 verdict and the new Beta verdict, side by side.
    Pure shadow — computes both, decides nothing. n8 mirrors Slice 1's _prior_vetoes_reflex
    defaults (conf>=0.6, success<=0.4); beta vetoes when P(rate<=max_success) >= credence."""
    buckets: dict[tuple[str, str], list[str]] = {}
    for row in store.iter_rows_for_priors():
        key = (row["request_class_id"], row["chosen_tool"] or "")
        buckets.setdefault(key, []).append(row["outcome_quality"])
    out: dict[tuple[str, str], BeliefComparison] = {}
    for (cls, tool), outcomes in buckets.items():
        n = len(outcomes)
        usable = sum(1 for q in outcomes if q in _GOOD)
        rate = usable / n if n else 0.0
        n8_conf = _confidence(n) if n >= min_observations else 0.0
        n8_veto = bool(n8_conf >= n8_min_conf and rate <= max_success)
        mean, p_below = beta_belief(usable, n, prior_alpha=prior_alpha, prior_beta=prior_beta,
                                    max_success=max_success)
        beta_veto = bool(p_below >= credence)
        out[(cls, tool)] = BeliefComparison(cls, tool, n, usable, n8_conf, rate, n8_veto,
                                            mean, p_below, beta_veto)
    return out
```

- [ ] **Step 3: Run; confirm all PASS** (esp. `test_mixed_n8_overclaims_beta_abstains` — the keystone). Ruff: `/home/rohit/maez/.venv/bin/python -m ruff check core/routing/observation/priors.py tests/test_beta_belief.py`.

- [ ] **Step 4: Commit** (pure module — no `## Predicted effect`):

```bash
git add core/routing/observation/priors.py tests/test_beta_belief.py
git commit -m "feat(routing-priors): Beta-Binomial belief + side-by-side n8-vs-Beta comparison (pure)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Shadow-log the comparison + a default-off Beta veto-swap (FULL two-stage — live path)

**Files:** Modify `daemon/maez_daemon.py` (2 seams). Test `tests/test_beta_shadow_seam.py`.

- [ ] **Step 1: Write the failing test** — a pure helper so the verdict-swap is testable:

```python
import os, unittest
os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test")
os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")

class BetaSeamTest(unittest.TestCase):
    def test_beta_flags_default_off(self):
        from daemon.maez_daemon import _routing_beta_shadow_enabled, _routing_beta_veto_enabled
        os.environ.pop("MAEZ_ROUTING_BETA_SHADOW", None)
        os.environ.pop("MAEZ_ROUTING_BETA_ENABLED", None)
        self.assertFalse(_routing_beta_shadow_enabled())
        self.assertFalse(_routing_beta_veto_enabled())
    def test_beta_flags_on(self):
        from daemon.maez_daemon import _routing_beta_shadow_enabled, _routing_beta_veto_enabled
        os.environ["MAEZ_ROUTING_BETA_SHADOW"] = "1"; os.environ["MAEZ_ROUTING_BETA_ENABLED"] = "1"
        try:
            self.assertTrue(_routing_beta_shadow_enabled()); self.assertTrue(_routing_beta_veto_enabled())
        finally:
            os.environ.pop("MAEZ_ROUTING_BETA_SHADOW", None); os.environ.pop("MAEZ_ROUTING_BETA_ENABLED", None)
```
Run; confirm FAIL.

- [ ] **Step 2: Add the flag helpers** (module-level near `_veto_ledger_enabled`):
```python
def _routing_beta_shadow_enabled() -> bool:
    return os.environ.get("MAEZ_ROUTING_BETA_SHADOW") == "1"
def _routing_beta_veto_enabled() -> bool:
    return os.environ.get("MAEZ_ROUTING_BETA_ENABLED") == "1"
```
Run; the 2 tests PASS.

- [ ] **Step 3: Shadow-log the comparison** at the prior-consult seam (inside the existing `if SHADOW or ENABLED` block ~5910, after the `routing_prior_shadow` log). Init `_belief_cmp = None` near `_prior = None` (~5903). Then:
```python
        if _routing_beta_shadow_enabled() or _routing_beta_veto_enabled():
            try:
                from core.routing.observation.priors import compare_beliefs
                _belief_cmp = compare_beliefs(_default_store()).get((_cls, "web_search"))
                if _belief_cmp is not None:
                    logger.info("routing_belief_compare class=%s n=%s usable=%s n8_veto=%s beta_veto=%s "
                                "n8_conf=%.3f beta_p=%.3f", _cls, _belief_cmp.n, _belief_cmp.usable,
                                _belief_cmp.n8_would_veto, _belief_cmp.beta_would_veto,
                                _belief_cmp.n8_confidence, _belief_cmp.beta_p_below)
            except Exception as _be:
                logger.debug("routing belief compare skipped: %s", _be)
```
(`_cls` is already computed at 5914; ensure this runs after it. The whole block is inside the flag-gated consult, so scipy loads only when a Beta flag is on.)

- [ ] **Step 4: The default-off Beta veto-swap.** At the veto application, compute the verdict, swapping to Beta only when `MAEZ_ROUTING_BETA_ENABLED`:
```python
        _veto_decision = _prior_vetoes_reflex(_prior)
        if _routing_beta_veto_enabled() and _belief_cmp is not None:
            _veto_decision = _belief_cmp.beta_would_veto   # graduation: Beta replaces n/8 (owner-flipped)
        if os.environ.get("MAEZ_ROUTING_PRIORS_ENABLED") == "1" and _veto_decision \
           and _override_event_id is None:
            _reflex = False
            ...  # the Slice-3a veto-ledger record block is UNCHANGED below this
```
Read the real veto-application block (post-3a it has the `_override_event_id is None` + the ledger record). Replace ONLY the `_prior_vetoes_reflex(_prior)` test with `_veto_decision`; leave the ledger record + override logic intact.

- [ ] **Step 5: Off = byte-identical.** Both Beta flags off → `_belief_cmp` stays None, `_veto_decision == _prior_vetoes_reflex(_prior)` (the swap `if` is False), no scipy import, no log → the veto is exactly Slice 3a/1. State how you confirmed.

- [ ] **Step 6: Run + ruff + commit** (behavior commit — `## Predicted effect`):
```bash
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_beta_shadow_seam tests.test_beta_belief tests.test_routing_priors_veto_seam -v
/home/rohit/maez/.venv/bin/python -m ruff check daemon/maez_daemon.py
git add daemon/maez_daemon.py tests/test_beta_shadow_seam.py
git commit -m "feat(routing): shadow-log n8-vs-Beta belief + default-off Beta veto-swap

## Predicted effect
With MAEZ_ROUTING_BETA_SHADOW=1, each reflex-eligible turn logs routing_belief_compare (n/8 vs Beta verdicts)
- NO behavior change. With MAEZ_ROUTING_BETA_ENABLED=1 (NOT flipped here), the veto would use Beta's verdict
instead of n/8. Both off => byte-identical to Slice 1/3a. scipy loads only when a Beta flag is on.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Calibration receipt + whole-slice green + handoff (STOP at the review gate)

**Files:** Create `docs/handoffs/2026-06-20-slice3b-handoff.md` (with the calibration table).

- [ ] **Step 1: Green + ruff.** Run `tests.test_beta_belief tests.test_beta_shadow_seam tests.test_routing_priors tests.test_routing_priors_veto_seam tests.test_veto_ledger tests.test_veto_ledger_seams` → all OK; ruff clean.

- [ ] **Step 2: Generate the calibration table (the "provably saner" artifact).** Run a throwaway snippet (do NOT commit it) that prints `compare_beliefs`-style verdicts across scenarios and paste the table into the handoff:
```bash
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -c "
from core.routing.observation.priors import beta_belief, _confidence
for label, usable, n in [('thin-2',0,2),('3-streak',0,3),('4-streak',0,4),('5-streak',0,5),
                          ('mixed-3of5',2,5),('mixed-2of4',2,4),('useful-5',5,5)]:
    rate = usable/n; n8c = _confidence(n) if n>=3 else 0.0
    n8v = n8c>=0.6 and rate<=0.4
    _, p = beta_belief(usable, n); bv = p>=0.9
    print(f'{label:12} n={n} usable={usable} rate={rate:.2f} | n8_conf={n8c:.2f} n8_veto={n8v} | beta_p={p:.2f} beta_veto={bv}')
"
```
The handoff MUST show: thin → both abstain; consistent streak → both veto (gate 4); **mixed → n8 vetoes but Beta abstains (gate 5)**; useful → neither vetoes.

- [ ] **Step 3: Off byte-identical confirm** — both Beta flags unset → no scipy import, no comparison, veto uses `n/8` exactly as Slice 1/3a.

- [ ] **Step 4: Handoff** — Codex anchors: (1) off=byte-identical (both flags); (2) Beta is pure/shadow — `learn_priors`/`_prior_vetoes_reflex` n/8 path untouched and still the live veto; (3) the five gates, esp. the **mixed-evidence divergence** (the calibration table is the witness, not "it vetoes Barchart"); (4) scipy lazy-loaded only when a flag is on; (5) `MAEZ_ROUTING_BETA_ENABLED` shipped default-off — graduation is an owner flag-flip AFTER reviewing the receipts, not a code change; (6) Beta prior+credence are FIXED in 3b (3c earns them); (7) untouched: 3a ledger, strict honesty gate, S7, Telegram, time-sense. **Owner-breath:** restart `maez`, set `MAEZ_ROUTING_BETA_SHADOW=1`; live some "today's signals" turns; `grep routing_belief_compare` — confirm Beta reproduces the Barchart veto (agreement on the consistent class) live, and review the calibration table for the mixed-evidence sanity. ONLY THEN consider `MAEZ_ROUTING_BETA_ENABLED=1`. No autonomous check.

- [ ] **Step 5: Commit handoff. STOP** (no merge/restart/flag-flip — owner-sovereign).

---

## Self-Review

**Spec coverage:** Beta-Binomial belief (posterior + credible statistic) → Task 1 `beta_belief`; side-by-side shadow (gate 1) → `compare_beliefs` + Task 2 Step 3 log; skeptical prior / thin uncertain (gate 2) → `test_beta_belief_thin_stays_uncertain` + `test_thin_both_abstain`; no behavior change until proven (gate 3) → both flags default-off + ENABLED not flipped + Task 2 Step 5; Barchart still vetoes but not sufficient (gate 4) → `test_consistent_both_veto` + the handoff framing; mixed → Beta less confident (gate 5) → `test_mixed_n8_overclaims_beta_abstains` (the keystone) + the calibration table; fixed prior in 3b, earned in 3c → noted in `beta_belief` docstring + handoff; off=byte-identical → Task 2 Step 5. OUT (3c earned threshold) untouched. Covered.

**Placeholder scan:** scipy is lazy-imported inside `beta_belief` (only runs when a flag is on, Task 0 Step 2 confirms it's heavy). The veto-swap (Task 2 Step 4) says "read the real post-3a veto-application block and replace ONLY the `_prior_vetoes_reflex(_prior)` test" — Task 0 Step 1 pins the line. No TBD; all code concrete.

**Type consistency:** `beta_belief(usable, n, *, prior_alpha, prior_beta, max_success) -> (mean, p_below)`; `compare_beliefs(store, *, min_observations, n8_min_conf, max_success, credence, prior_alpha, prior_beta) -> dict[(cls,tool)->BeliefComparison]`; `BeliefComparison` fields used identically in Task 1 tests + Task 2 seam (`.n`, `.usable`, `.n8_would_veto`, `.beta_would_veto`, `.n8_confidence`, `.beta_p_below`, `.beta_mean`). `_confidence`/`_GOOD` reused from Slice 1 unchanged. The n8 verdict mirrors `_prior_vetoes_reflex` defaults (0.6/0.4).
