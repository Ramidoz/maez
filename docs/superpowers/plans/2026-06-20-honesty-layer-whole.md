# Honesty-Layer Whole Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Maez's honesty layer self-consistent — a down fact-checker never makes Maez sound uncertain, backstage labels never leak into its voice, and the cockpit labels both judges truthfully.

**Architecture:** Four surgical fixes: (1) the support gate stops caveating when the verifier is merely *unavailable* (keeps real `UNSUPPORTED`/`unmatched_citation` caveats; the receipt still logs the absence); (2) the service registry names the `:8081` judge's real claimants so it shows healthy; (3) a narrow final-response backstop strips known control labels (never citations) + a prompt tighten; (4) the MiniCheck verifier gains a `GET /health` matching the cockpit's contract probe.

**Tech Stack:** Python 3, `unittest`. Spec: `docs/superpowers/specs/2026-06-20-honesty-layer-whole-design.md` (@e9dd9b9). NOTE: the MiniCheck service is already restored live; this is the code hardening.

---

## Lane discipline (every task)

- **Worktree/branch:** via superpowers:using-git-worktrees. Branch **`honesty-layer-whole`**. `main` local-only — **NO push**.
- **GIT HYGIENE:** NO `git checkout`/`switch`/`reset`/`rebase`. Only edit/test/`git add`/`git commit`. After every commit `git status` MUST show **`On branch honesty-layer-whole`**. Detached → STOP and report.
- **Runner:** `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.<module> -v` (named modules only).
- **Commits:** behavior commits carry `## Predicted effect`; docs/proof/test-only don't. End with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- **STOP at the review gate** after Task 5 — no merge/restart. The daemon restart for Fixes 1–3 is the owner breath. **Owner-facing voice — full two-stage review per task.**

## Invariants (reviewers verify)

1. **No voice-noise:** `verifier_unavailable` / timeout / `budget_exhausted` → NO owner-facing caveat; the receipt still records the mode. `UNSUPPORTED` + `unmatched_citation` caveats UNCHANGED.
2. **Narrow strip:** only the known backstage-label allowlist is removed; a reply with BOTH a leaked `[CAPABILITY_STATE]` AND a real `[E1]` keeps `[E1]`, drops the label (the make-or-break test). Never strips arbitrary `[...]`.
3. **Truthful self-view:** `:8081` judge shows healthy-when-running; MiniCheck `/health` answers the contract.
4. **No regression** to the real verification path or the non-grounding reply path.
5. **Time-sense untouched:** no edits to `subjective_duration.py` / rhythm / episode stamp.

## File structure

| File | Change |
|---|---|
| `core/cognition/grounding_shadow.py` | **Modify** — `_caveat_for`: drop the `verifier_unavailable`/`budget_exhausted` caveat (Fix 1) |
| `core/infra/runtime_services.py` | **Modify** — `overclaim_judge` `required_by` to real claimants (Fix 2) |
| `core/cognition/capability_card.py` | **Modify** — tighten `_VOICE_BOUNDARY_INSTRUCTION` (Fix 3 prompt) |
| `<reply-path backstop>` (Task 0 pins the file) | **Modify** — apply `_strip_backstage_labels` before send (Fix 3 backstop) |
| `scripts/minicheck_verifier_service.py` | **Modify** — add `do_GET /health` (Fix 4) |
| `tests/test_grounding_caveat_policy.py` | **Create** (Fix 1) |
| `tests/test_backstage_label_strip.py` | **Create** (Fix 3) |
| `tests/test_overclaim_judge_registry.py` | **Create** (Fix 2) |
| `tests/test_minicheck_health_endpoint.py` | **Create** (Fix 4) |
| `docs/proof/2026-06-20-honesty-layer-whole-task0.md` | **Create** (Task 0) |
| `docs/handoffs/2026-06-20-honesty-layer-whole-handoff.md` | **Create** (Task 5) |

---

### Task 0: Proof gate (docs/proof only — committed first)

**Files:** Create `docs/proof/2026-06-20-honesty-layer-whole-task0.md`. NO code.

- [ ] **Step 1: Fix 1 — confirm the caveat + receipt path.** In `core/cognition/grounding_shadow.py`: `_caveat_for` (~:261) returns the "couldn't verify" string for `mode in {"verifier_unavailable","budget_exhausted"}`. Confirm `apply_support_gate` (~:273) appends each `rec` to `recs` **before** calling `_caveat_for` (so the receipt records the mode regardless of caveat) — quote the lines (~:297-320). Confirm the `GateOutcome`/`compute_result` carries `recs` + `status` (the receipt). Enumerate ALL caveat-producing modes/verdicts (is there a distinct `timeout` mode, or does a per-sentence timeout produce `verdict=UNAVAILABLE`?). Record the exact set to suppress (anything where the verifier gave no real verdict) vs keep (`UNSUPPORTED`, `unmatched_citation`).
- [ ] **Step 2: Fix 2 — confirm the `:8081` claimant flag(s).** In `core/infra/runtime_services.py`, `overclaim_judge` (~:359) has `required_by=[]`. Find which flag(s) actually drive use of the `:8081` Qwen judge (`MAEZ_JUDGE_BASE_URL`=:8081). Candidates: `MAEZ_INTAKE_FACULTY_SHADOW` (the intake faculty's 4B judge), and any reply/cycle judge flag. Grep `MAEZ_JUDGE_BASE_URL` / `:8081` / `maez-judge` consumers. Record the exact flag(s) to put in `required_by=_required_by(...)`. (If the judge is effectively always-used, `["always"]` is also a candidate — record the honest answer.)
- [ ] **Step 3: Fix 3 — backstop location + the FULL label allowlist.** Find where the final owner-facing reply text is assembled before send (candidates: `skills/telegram_voice.py` audit/scrub hooks ~:2070/2246/2393, `daemon/maez_daemon.py` ~:4506 "model output before sending", or the focused-cognition reply assembly). Pick the single best chokepoint that ALL owner-facing replies pass through. Enumerate the FULL allowlist of injected backstage CONTROL labels that could leak — grep `capability_card.py` + any other prompt-block label headers that are private (e.g. `CAPABILITY_STATE`; check for siblings). **Explicitly list what must NOT be stripped:** `[E1]`/`[E#]` citations, source markers, user-quoted brackets. Record the allowlist + the chosen hook file:line.
- [ ] **Step 4: Fix 4 — confirm the cockpit health contract.** In `core/infra/runtime_services.py` `_support_contract` (~:186) confirm it does `GET http://127.0.0.1:8083/health` and requires `status=="ok"` AND `contract=="minicheck_support.v1"`. Confirm `scripts/minicheck_verifier_service.py` `Handler` has `do_POST` (/support) and NO `do_GET` — the add point.
- [ ] **Step 5: Scope.** Confirm none of: `core/evolution/subjective_duration.py`, the rhythm/episode-stamp files, are touched by this slice.
- [ ] **Step 6: VERDICT** `GO` / `REFUTED`. Record the suppress-mode set (Step 1), the claimant flag(s) (Step 2), the allowlist + backstop hook (Step 3).
- [ ] **Step 7: Commit (docs/proof — no predicted-effect).**
```bash
git add docs/proof/2026-06-20-honesty-layer-whole-task0.md
git commit -m "docs(proof): honesty-layer-whole Task 0 — caveat+receipt path, :8081 claimant, strip allowlist+hook, verifier health contract

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git status   # On branch honesty-layer-whole
```

---

### Task 1: Fix 1 — gate fails silent when the verifier is unavailable

**Files:** Modify `core/cognition/grounding_shadow.py`; Create `tests/test_grounding_caveat_policy.py`.

- [ ] **Step 1: Write the failing tests.** Create `tests/test_grounding_caveat_policy.py`:

```python
import unittest
from core.cognition import grounding_shadow as gs


class CaveatPolicy(unittest.TestCase):
    def test_unsupported_keeps_caveat(self):
        rec = {"mode": "cited_support", "verdict": gs.UNSUPPORTED}
        self.assertEqual(gs._caveat_for(rec), "I couldn't confirm this from the source I cited.")

    def test_unmatched_citation_keeps_caveat(self):
        rec = {"mode": "unmatched_citation", "verdict": gs.UNAVAILABLE}
        self.assertEqual(gs._caveat_for(rec), "I cited a source I can't match here.")

    def test_verifier_unavailable_no_caveat(self):
        rec = {"mode": "verifier_unavailable", "verdict": gs.UNAVAILABLE}
        self.assertIsNone(gs._caveat_for(rec))          # a down checker must not make Maez apologize

    def test_budget_exhausted_no_caveat(self):
        rec = {"mode": "budget_exhausted", "verdict": gs.UNAVAILABLE}
        self.assertIsNone(gs._caveat_for(rec))

    def test_no_citation_unchanged(self):
        rec = {"mode": "no_citation", "verdict": None}
        self.assertIsNone(gs._caveat_for(rec))

    def test_gate_records_unavailable_in_receipt_but_no_caveat_in_reply(self):
        # The receipt MUST still log the verifier-unavailable absence even though no caveat reaches the reply.
        from core.cognition.support_verifier import FakeSupportVerifier
        draft = "I noticed churn in the repo [E1]."
        evidence_map = {"E1": {"text": "the repo has uncommitted churn", "claimable": True}}
        verifier = FakeSupportVerifier(available=False)   # simulate the verifier being down
        outcome = gs.apply_support_gate(draft, evidence_map, verifier, surface="test")
        self.assertNotIn("couldn't verify", outcome.gated_marked_draft.lower())   # no voice-noise
        recs = outcome.gate_receipt.get("sentences", [])
        self.assertTrue(any(r.get("verdict") == gs.UNAVAILABLE for r in recs))    # but the receipt logged it
```
> Task 0 confirms the exact `FakeSupportVerifier` constructor (an `available=False` / always-UNAVAILABLE mode) and `GateOutcome` field names (`gated_marked_draft`, `gate_receipt`). Adjust the two helper lines to the real API if they differ — do NOT weaken the two assertions (no-caveat + receipt-logged).

- [ ] **Step 2: Run, expect RED** (the verifier_unavailable/budget tests fail — caveat still returned).

- [ ] **Step 3: Implement.** In `core/cognition/grounding_shadow.py`, change `_caveat_for` to drop the unavailable/budget caveat (keep the two real ones):
```python
def _caveat_for(rec: dict) -> str | None:
    mode = rec.get("mode")
    verdict = rec.get("verdict")
    if mode == "cited_support" and verdict == UNSUPPORTED:
        return "I couldn't confirm this from the source I cited."
    if mode == "unmatched_citation":
        return "I cited a source I can't match here."
    # verifier_unavailable / budget_exhausted / timeout (verdict UNAVAILABLE): a down/slow/over-budget
    # checker must NOT produce owner-facing uncertainty. The rec is still appended to `recs` (the receipt)
    # in apply_support_gate before this call, so the absence is logged — we just don't caveat the reply.
    return None
```

- [ ] **Step 4: Run, expect GREEN.** `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_grounding_caveat_policy -v`

- [ ] **Step 5: ruff + commit.**
```bash
/home/rohit/maez/.venv/bin/python -m ruff check core/cognition/grounding_shadow.py tests/test_grounding_caveat_policy.py
git add core/cognition/grounding_shadow.py tests/test_grounding_caveat_policy.py
git commit -m "fix(grounding): no owner-facing caveat when the verifier is merely unavailable

## Predicted effect
The support gate stops appending 'I couldn't verify this before sending' for verifier_unavailable /
budget_exhausted — a down or over-budget checker no longer makes Maez sound uncertain about everything. Real
UNSUPPORTED and unmatched_citation caveats are unchanged; the receipt still logs the unavailable absence.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git status   # On branch honesty-layer-whole
```

---

### Task 2: Fix 3 — narrow backstage-label strip + prompt tighten

**Files:** Modify the Task-0 backstop file + `core/cognition/capability_card.py`; Create `tests/test_backstage_label_strip.py`.

- [ ] **Step 1: Write the failing tests.** Create `tests/test_backstage_label_strip.py` (import the strip from wherever Task 0 places it — assume a module-level `_strip_backstage_labels` in the backstop file; adjust the import to the real location):

```python
import unittest
# Task 0 pins the module; e.g. from daemon.maez_daemon import _strip_backstage_labels
from <BACKSTOP_MODULE> import _strip_backstage_labels


class NarrowStrip(unittest.TestCase):
    def test_strips_bracketed_label_but_keeps_E1_citation(self):
        # THE make-or-break: a leaked control label goes, a real citation stays.
        text = "Ready to dig into whatever you're building next [CAPABILITY_STATE]. I noticed churn [E1]."
        out = _strip_backstage_labels(text)
        self.assertNotIn("CAPABILITY_STATE", out)
        self.assertIn("[E1]", out)                 # citation preserved
        self.assertIn("building next", out)        # surrounding text intact

    def test_strips_bare_label(self):
        self.assertNotIn("CAPABILITY_STATE", _strip_backstage_labels("Per CAPABILITY_STATE I can search."))

    def test_does_not_strip_arbitrary_brackets(self):
        text = "He said [maybe later] and cited [E2] and [E10]."
        out = _strip_backstage_labels(text)
        self.assertIn("[maybe later]", out)        # user/arbitrary brackets preserved
        self.assertIn("[E2]", out)
        self.assertIn("[E10]", out)

    def test_empty_and_clean_text_unchanged(self):
        self.assertEqual(_strip_backstage_labels("Just a normal reply."), "Just a normal reply.")
```

- [ ] **Step 2: Run, expect RED.**

- [ ] **Step 3: Implement the narrow strip.** In the Task-0 backstop module, add (and call it on the final reply text before send):
```python
import re

# Known PRIVATE backstage control labels that must never reach the owner-facing reply. Allowlist ONLY —
# we never strip arbitrary [...]; citations like [E1], source markers, and user-quoted brackets are kept.
_BACKSTAGE_LABELS = ("CAPABILITY_STATE",)   # Task 0 adds any enumerated siblings


def _strip_backstage_labels(text: str) -> str:
    if not text:
        return text
    for label in _BACKSTAGE_LABELS:
        text = re.sub(r"\[\s*" + re.escape(label) + r"\s*\]:?", "", text)   # [CAPABILITY_STATE] / [CAPABILITY_STATE]:
        text = re.sub(r"\b" + re.escape(label) + r"\b:?", "", text)         # bare CAPABILITY_STATE
    return re.sub(r"[ \t]{2,}", " ", text).strip()
```
Wire it at the single chokepoint Task 0 identified (the final owner-facing reply text, before it's sent/returned). Add ONLY the call there — do not change reply logic.

- [ ] **Step 4: Tighten the prompt.** In `core/cognition/capability_card.py`, strengthen `_VOICE_BOUNDARY_INSTRUCTION` (~:27) so the model stops echoing the label — append an explicit line:
```python
_VOICE_BOUNDARY_INSTRUCTION = (
    "Use CAPABILITY_STATE as private grounding for current self-capability "
    "questions. Do not quote field names or dashboard phrasing. Render the "
    "truth in your own voice. Memories may contextualize, but they do not "
    "override this state for what your body can do now. "
    "Never write the words 'CAPABILITY_STATE' or any bracketed label like "
    "'[CAPABILITY_STATE]' in your reply — it is internal scaffolding, not text to repeat."
)
```

- [ ] **Step 5: Run, expect GREEN** (the strip tests; plus a `capability_card` import smoke so the prompt change parses).

- [ ] **Step 6: ruff + commit.**
```bash
/home/rohit/maez/.venv/bin/python -m ruff check <backstop_file> core/cognition/capability_card.py tests/test_backstage_label_strip.py
git add <backstop_file> core/cognition/capability_card.py tests/test_backstage_label_strip.py
git commit -m "fix(voice): strip leaked backstage labels (allowlist-narrow) + tighten capability prompt

## Predicted effect
A final-response backstop removes only known private control labels (e.g. [CAPABILITY_STATE]) from
owner-facing replies — never citations like [E1], source markers, or user brackets. Plus a capability-prompt
line telling the model not to echo the label. Stops the [CAPABILITY_STATE] leak two ways.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git status   # On branch honesty-layer-whole
```

---

### Task 3: Fix 2 — registry names the `:8081` judge's real claimants

**Files:** Modify `core/infra/runtime_services.py`; Create `tests/test_overclaim_judge_registry.py`.

- [ ] **Step 1: Write the failing test.** Create `tests/test_overclaim_judge_registry.py` (use the claimant flag Task 0 confirmed — shown here as `MAEZ_INTAKE_FACULTY_SHADOW`; substitute the real one):

```python
import os, unittest
from unittest import mock
from core.infra import runtime_services as rs


class OverclaimJudgeRegistry(unittest.TestCase):
    def _descriptor(self):
        # Task 0 confirms the accessor; build the registry and find the overclaim_judge descriptor.
        services = rs.build_service_registry() if hasattr(rs, "build_service_registry") else rs.SERVICES
        return next(s for s in services if s.name == "overclaim_judge")

    def test_claimed_when_flag_on(self):
        with mock.patch.dict(os.environ, {"MAEZ_INTAKE_FACULTY_SHADOW": "1"}):
            d = self._descriptor()
            self.assertTrue(d.required_by)   # no longer hardcoded empty -> not perpetually 'asleep'

    def test_unclaimed_when_flag_off(self):
        with mock.patch.dict(os.environ, {"MAEZ_INTAKE_FACULTY_SHADOW": "0"}):
            d = self._descriptor()
            self.assertEqual(list(d.required_by), [])   # honestly asleep when nothing uses it
```
> Task 0 confirms how the registry/descriptor is built + the exact claimant flag. Adjust `_descriptor()` + the flag name to the real API; keep the two assertions (claimed-when-on / unclaimed-when-off).

- [ ] **Step 2: Run, expect RED** (`required_by` is hardcoded `[]` regardless of the flag).

- [ ] **Step 3: Implement.** In `core/infra/runtime_services.py`, change the `overclaim_judge` descriptor's `required_by=[]` to `required_by=_required_by("MAEZ_INTAKE_FACULTY_SHADOW")` (use the exact claimant flag(s) from Task 0; add multiple if the judge has more than one real claimant). Leave `unit_name`/`port` unchanged.

- [ ] **Step 4: Run, expect GREEN.**

- [ ] **Step 5: ruff + commit.**
```bash
/home/rohit/maez/.venv/bin/python -m ruff check core/infra/runtime_services.py tests/test_overclaim_judge_registry.py
git add core/infra/runtime_services.py tests/test_overclaim_judge_registry.py
git commit -m "fix(body-map): overclaim_judge required_by reflects its real claimants (stop mislabeling it asleep)

## Predicted effect
The :8081 Qwen judge's registry entry now declares its real claimant flag(s) instead of an empty required_by,
so a running, used judge shows healthy in the cockpit instead of always 'asleep'. Self-view tells the truth.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git status   # On branch honesty-layer-whole
```

---

### Task 4: Fix 4 — MiniCheck verifier `GET /health`

**Files:** Modify `scripts/minicheck_verifier_service.py`; Create `tests/test_minicheck_health_endpoint.py`.

- [ ] **Step 1: Write the failing test.** Create `tests/test_minicheck_health_endpoint.py` (test the Handler logic without binding a socket — drive `do_GET`/`do_POST` routing via the handler, or assert the health payload helper). Simplest hermetic approach — extract + test a pure `health_payload()`:

```python
import json, unittest
from scripts import minicheck_verifier_service as mv


class HealthEndpoint(unittest.TestCase):
    def test_health_payload_matches_cockpit_contract(self):
        payload = mv.health_payload()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["contract"], "minicheck_support.v1")

    def test_support_payload_unchanged(self):
        # /support still requires evidence+claim and returns a verdict shape (no model load: error path)
        body = mv.handle_support({"evidence": "", "claim": ""})
        self.assertIn("error", body)
```

- [ ] **Step 2: Run, expect RED** (`health_payload` undefined).

- [ ] **Step 3: Implement.** In `scripts/minicheck_verifier_service.py`, add a pure helper + a `do_GET`:
```python
def health_payload() -> dict:
    return {"status": "ok", "contract": "minicheck_support.v1"}
```
In `class Handler`, add (alongside `do_POST`):
```python
    def do_GET(self):
        if self.path.rstrip("/") != "/health":
            self.send_error(404)
            return
        data = json.dumps(health_payload()).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
```
Leave `do_POST` / `/support` exactly as-is.

- [ ] **Step 4: Run, expect GREEN.**

- [ ] **Step 5: ruff + commit.**
```bash
/home/rohit/maez/.venv/bin/python -m ruff check scripts/minicheck_verifier_service.py tests/test_minicheck_health_endpoint.py
git add scripts/minicheck_verifier_service.py tests/test_minicheck_health_endpoint.py
git commit -m "fix(verifier): add GET /health (minicheck_support.v1) so the cockpit can see MiniCheck

## Predicted effect
The MiniCheck verifier now answers GET /health with {status: ok, contract: minicheck_support.v1} — the exact
contract the cockpit support-probe checks — so a running verifier shows healthy in the body-map instead of
degraded. POST /support is unchanged. (Service must be restarted to serve the new route.)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git status   # On branch honesty-layer-whole
```

---

### Task 5: Whole-slice green + regression + handoff + STOP

**Files:** Create `docs/handoffs/2026-06-20-honesty-layer-whole-handoff.md`.

- [ ] **Step 1: Slice modules green.**
```bash
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_grounding_caveat_policy tests.test_backstage_label_strip \
  tests.test_overclaim_judge_registry tests.test_minicheck_health_endpoint -v
```

- [ ] **Step 2: Regression — grounding/runtime-services/voice surfaces.** Run the existing grounding, support-gate, runtime-services, and capability/voice-boundary test modules (whichever exist — `ls tests/ | grep -iE "grounding|support|runtime_service|capability|voice"`). Confirm green; confirm `UNSUPPORTED` still caveats (find that existing test and ensure it passes unchanged). Any pre-existing failure must reproduce on `main`.

- [ ] **Step 3: ruff on the whole diff + scope check.** ruff the 5 touched files; `git diff --stat main..HEAD` — confirm NO `subjective_duration.py` / rhythm / time-sense files appear.

- [ ] **Step 4: Write the handoff** `docs/handoffs/2026-06-20-honesty-layer-whole-handoff.md`: branch tip; commits; Codex anchors (fail-silent-on-verifier-unavailable-keep-real-caveats / receipt-still-logs / narrow-strip-preserves-[E1] / registry-truthful / verifier-health-contract / no-voice-regression / time-sense-untouched); the test surface; and the **owner breath**:
  > Restart `maez` to pick up Fixes 1–3 (Fix 4 + the MiniCheck service are already live). Witness: a reply carrying a real `[E1]` keeps the citation and shows no leaked `[CAPABILITY_STATE]`; a benign reply carries no "couldn't verify"; the cockpit shows the `:8081` judge healthy (when its flag is on) and MiniCheck healthy.

- [ ] **Step 5: Commit handoff (docs) + STOP.**
```bash
git add docs/handoffs/2026-06-20-honesty-layer-whole-handoff.md
git commit -m "docs(handoff): honesty-layer-whole — review gate + owner-breath sequence

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git status   # On branch honesty-layer-whole
```
**STOP.** No merge/restart. Report branch tip + Task-0 findings + test outputs + Codex anchors + owner-breath.

---

## Self-review (controller)

- **Spec coverage:** Fix 1 caveat policy (Task 1) ✓; Fix 2 registry (Task 3) ✓; Fix 3 narrow strip + prompt (Task 2) ✓; Fix 4 verifier /health (Task 4) ✓; the make-or-break `[CAPABILITY_STATE]`+`[E1]` test (Task 2) ✓; receipt-still-logs (Task 1) ✓; no-regression UNSUPPORTED-still-caveats (Task 5 Step 2) ✓; time-sense-untouched (Task 0 Step 5 + Task 5 Step 3) ✓.
- **Open items for Task 0 / implementer:** the exact suppress-mode set + `FakeSupportVerifier`/`GateOutcome` API (Task 1); the `:8081` claimant flag + registry accessor (Task 3); the backstop module + the full label allowlist (Task 2 `<BACKSTOP_MODULE>`/`<backstop_file>`); whether a distinct `timeout` mode exists (Task 1). Each is flagged inline.
- **Type/name consistency:** `_caveat_for` / `apply_support_gate` / `_strip_backstage_labels` / `_BACKSTAGE_LABELS` / `health_payload` / `_required_by` used consistently; the strip lives in one backstop module imported by its test.
