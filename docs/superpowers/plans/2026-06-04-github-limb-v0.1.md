# GitHub Limb v0.1 — Boundary Honesty Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make GitHub owner-account data wear an `owner_account_context` wristband that survives to the cloud egress chokepoint (proven by a canary the proxy refuses), and stop Maez from unattended-publishing itself to public GitHub.

**Architecture:** Two boundary fixes, no digestion. (1) The GitHub context block becomes a `ProvenancedText(owner_account_context)` at the producer (`github_skill`); the daemon keeps a dual view — `.text` for the local 27B cycle prompt, the `ProvenancedText` handle for any cloud-bound assembly; a canary driven through the **real** subscription-proxy path proves 403 / adapter-not-called. (2) The unattended `publish_nightly()` call is removed from the journal path. v0.1 supplies the *first producer* of an egress lock that already exists and is already enforced — it does **not** modify the gate.

**Tech Stack:** Python 3, `unittest` (run with `.venv/bin/python -B -m unittest`, **not pytest**), the existing `core/egress` provenance/gate system, the FastAPI subscription proxy.

---

## Spec

Source spec: `docs/superpowers/specs/2026-06-04-github-limb-v0.1-design.md`. The five locked acceptance rules:
1. **Producer:** GitHub owner-account block is `ProvenancedText(owner_account_context)` (whole block, incl. trending).
2. **Survival:** any egress-visible path to `claude_tier` preserves that span into `maez_egress_segments` — no flatten-to-string en route.
3. **Witness:** canary GitHub owner-account text reaches the real proxy path and is **403, adapter not called**, reason `owner_account_context_blocked_default`, holding even with `redaction_allowed=True`, telemetry content-free.
4. **Fail-closed honesty:** if the diffuse memory/recall route cannot preserve provenance without the digestion slice, **name that residual gap** — do not claim full closure.
5. **Auto-push:** remove the unattended `publish_nightly()` from the journal path; future publishing is a deliberate owner action only.

**Hard constraints:**
- **No "tag then flatten."** The witness is the proxy refusing the span — not any intermediate label.
- **`ProvenancedText` is not a drop-in for the prompt string.** Preserve two views: `block.text` (plain) for local cognition; `block` (spans) for cloud-bound assembly.
- **Do NOT modify `core/egress/gate.py`.** v0.1 only supplies the first producer. Adding a `ProvenancedText.owner_account_context()` factory in `core/egress/provenance.py` is producer API, not gate logic — allowed.

---

## File Structure

| File | Change | Responsibility |
|---|---|---|
| `core/egress/provenance.py` | Modify (add one classmethod) | Producer API: `ProvenancedText.owner_account_context(text, *, source_ref)` — the missing factory (every other origin class already has one). |
| `skills/github_skill.py` | Modify (`get_context_block`) | Producer: return `ProvenancedText(owner_account_context)` wrapping the whole block (incl. trending). `.text` is byte-identical to today's string. |
| `daemon/maez_daemon.py` | Modify (lines ~4296-4303 inject; ~7623-7633 publish) | Dual view: `.text` for local prompt + cycle candidate; preserve the `ProvenancedText` handle on `self._last_github_block`. Remove the unattended publish call. |
| `tests/test_github_owner_account_provenance.py` | Create | Producer unit tests + the producer→proxy canary witness. |
| `tests/test_github_publish_retired.py` | Create | Guard: the journal path performs no unattended `publish_nightly()` / `git push`. |
| `docs/superpowers/specs/2026-06-04-github-limb-v0.1-design.md` | Modify (append residual-gap finding) | Record the verified live/latent path finding + the named diffuse-path residual gap. |

**Reference (read-only — do NOT modify):** `core/egress/gate.py` (`OWNER_ACCOUNT_CONTEXT`, `KNOWN_ORIGINS`, the categorical block at lines 197-232), `core/subscription_proxy/server.py` (`_build_egress_request` ~446, enforcement ~690-710), `core/routing/claude_tier.py` (the `maez_egress_segments` assembly), `tests/test_subscription_proxy_owner_account_enforcement.py` (the canary pattern), `tests/test_egress_telegram_producer_threading.py` (the producer-threading pattern).

---

### Task 1: Producer API — `ProvenancedText.owner_account_context()`

**Files:**
- Modify: `core/egress/provenance.py` (add a classmethod alongside the existing `owner_message_context` at lines 173-182)
- Test: `tests/test_github_owner_account_provenance.py` (create)

Context: `core/egress/provenance.py` already has a `ProvenancedText` factory for every origin class **except** `owner_account_context` — because nothing has ever produced it ("nothing tags it yet"). `owner_account_context` is in `KNOWN_ORIGINS` (gate.py:56-64), so a `ProvenanceSpan` carrying it will **not** be downgraded to `unclassified` (provenance.py:35). It is categorically blocked regardless of `redaction_allowed` (gate.py:197-232), so the factory sets `redaction_allowed=False` (no point allowing redaction on a categorical block).

- [ ] **Step 1: Write the failing test**

Create `tests/test_github_owner_account_provenance.py`:

```python
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""GitHub Limb v0.1 — owner-account provenance survives to the egress chokepoint.

The producer (github_skill) must emit ProvenancedText(owner_account_context),
and that span must reach the real subscription-proxy path and be refused (403,
adapter not called). No "tag then flatten": the witness is the door refusing it.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class OwnerAccountFactoryTests(unittest.TestCase):
    def test_factory_emits_owner_account_context_span_not_downgraded(self):
        from core.egress.provenance import ProvenancedText

        pt = ProvenancedText.owner_account_context(
            "private repo: secret-thing", source_ref="github:user_repos"
        )
        self.assertEqual(len(pt.spans), 1)
        span = pt.spans[0]
        self.assertEqual(span.origin_class, "owner_account_context")  # NOT downgraded
        self.assertFalse(span.redaction_allowed)                      # categorical block
        self.assertEqual(span.text, "private repo: secret-thing")
        self.assertEqual(pt.text, "private repo: secret-thing")       # dual view: .text plain
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -B -m unittest tests.test_github_owner_account_provenance.OwnerAccountFactoryTests -v`
Expected: FAIL — `AttributeError: type object 'ProvenancedText' has no attribute 'owner_account_context'`.

- [ ] **Step 3: Write minimal implementation**

In `core/egress/provenance.py`, add this classmethod immediately after the `owner_message_context` classmethod (after line 182):

```python
    @classmethod
    def owner_account_context(
        cls,
        text: str,
        *,
        source_ref: str,
    ) -> "ProvenancedText":
        # Personal-account-derived data (GitHub/Reddit/Gmail/...). Categorical
        # cloud-egress block by default (gate.py OWNER_ACCOUNT_CONTEXT); the gate
        # ignores redaction_allowed for this class, so there is no point allowing
        # redaction — fail closed with redaction_allowed=False.
        return cls.from_spans([
            ProvenanceSpan(text, "owner_account_context", source_ref, False)
        ])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -B -m unittest tests.test_github_owner_account_provenance.OwnerAccountFactoryTests -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/egress/provenance.py tests/test_github_owner_account_provenance.py
git commit -m "feat(egress): ProvenancedText.owner_account_context producer factory"
```

---

### Task 2: GitHub producer emits `ProvenancedText(owner_account_context)`

**Files:**
- Modify: `skills/github_skill.py` (`get_context_block`, lines 161-195)
- Test: `tests/test_github_owner_account_provenance.py` (add a class)

Context: `get_context_block()` currently returns a plain `str` (the `[GITHUB]` block) or `""`/`"[GITHUB] Unavailable."`. The whole block — including the public "Trending AI" section — is stamped `owner_account_context` (fail-closed owner call: over-protecting public trending is harmless; under-protecting private owner-account context is not). `.text` must remain byte-identical to today's output so the local cycle prompt is unchanged.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_github_owner_account_provenance.py`:

```python
class GithubProducerTests(unittest.TestCase):
    def _skill_with_canary(self):
        from skills.github_skill import GitHubSkill

        skill = GitHubSkill.__new__(GitHubSkill)  # bypass __init__ network/secret load
        skill.enabled = True
        skill.username = "CANARY_USER"
        skill._cache = {}
        skill._cache_time = {}
        skill.cache_ttl = 300
        skill.token = "x"
        # Stub the fetchers so get_context_block builds a canary block, no network.
        skill.get_user_repos = lambda: [
            {"name": "CANARY_REPO", "private": True, "language": "Python",
             "updated_at": "2026-06-01T00:00:00Z", "description": "CANARY_DESC"}
        ]
        skill.get_recent_commits = lambda name, limit=1: []
        skill.get_user_activity = lambda: ["Pushed to CANARY_REPO: CANARY_MSG"]
        skill.get_trending_ai_repos = lambda n=5: []
        return skill

    def test_get_context_block_returns_owner_account_provenanced_text(self):
        from core.egress.provenance import ProvenancedText

        block = self._skill_with_canary().get_context_block()
        self.assertIsInstance(block, ProvenancedText)
        # whole block stamped owner_account_context (incl. any trending)
        self.assertTrue(block.spans)
        self.assertTrue(all(s.origin_class == "owner_account_context" for s in block.spans))
        # dual view: .text carries the human-readable block (the canary content)
        self.assertIn("CANARY_REPO", block.text)
        self.assertIn("[GITHUB]", block.text)

    def test_disabled_skill_returns_empty_provenanced_text(self):
        from core.egress.provenance import ProvenancedText
        from skills.github_skill import GitHubSkill

        skill = GitHubSkill.__new__(GitHubSkill)
        skill.enabled = False
        block = skill.get_context_block()
        self.assertIsInstance(block, ProvenancedText)
        self.assertFalse(block)            # __bool__ False — injection `if` skips it
        self.assertEqual(block.text, "")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -B -m unittest tests.test_github_owner_account_provenance.GithubProducerTests -v`
Expected: FAIL — `get_context_block` returns `str`, so `assertIsInstance(..., ProvenancedText)` fails.

- [ ] **Step 3: Write minimal implementation**

In `skills/github_skill.py`, add the import near the top (after `import requests`, line 14):

```python
from core.egress.provenance import ProvenancedText
```

Replace `get_context_block` (lines 161-195) so it builds the same string, then wraps it. Keep all existing block-building logic; only the return type changes:

```python
    def get_context_block(self) -> ProvenancedText:
        if not self.enabled:
            return ProvenancedText.owner_account_context(
                "", source_ref="github:disabled")
        try:
            repos = self.get_user_repos()
            active = sorted(repos, key=lambda r: r.get('updated_at', ''), reverse=True)[:5]
            activity = self.get_user_activity()
            trending = self.get_trending_ai_repos(5)

            lines = [f"[GITHUB] the owner has {len(repos)} repos."]

            if active:
                lines.append("Active repos:")
                for r in active:
                    vis = "private" if r.get('private') else "public"
                    desc = f" — {r.get('description', '')}" if r.get('description') else ""
                    lines.append(f"  {r['name']} ({r.get('language', '?')}, {vis}){desc}")
                    commits = self.get_recent_commits(r['name'], 1)
                    if commits:
                        lines.append(f"    Last: {commits[0]['date']} {commits[0]['message']}")

            if activity:
                lines.append("Recent activity:")
                for a in activity[:4]:
                    lines.append(f"  {a}")

            if trending:
                lines.append("Trending AI this week:")
                for t in trending[:4]:
                    lines.append(f"  {t['name']} ({t['stars']:,} stars) — {t['description'][:60]}")

            # v0.1 boundary honesty: the WHOLE block (incl. public trending) is
            # owner-account context — fail-closed. .text is byte-identical to the
            # previous string; the spans carry owner_account_context to egress.
            return ProvenancedText.owner_account_context(
                "\n".join(lines), source_ref="github:context_block")
        except Exception as e:
            logger.error("GitHub context failed: %s", e)
            return ProvenancedText.owner_account_context(
                "[GITHUB] Unavailable.", source_ref="github:error")
```

Also update the `__main__` block at the bottom (lines 198-201) so it still prints text:

```python
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    g = GitHubSkill()
    print(g.get_context_block().text)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -B -m unittest tests.test_github_owner_account_provenance.GithubProducerTests -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/github_skill.py tests/test_github_owner_account_provenance.py
git commit -m "feat(github): get_context_block emits ProvenancedText(owner_account_context)"
```

---

### Task 3: Daemon dual-view (don't break local cognition, don't flatten the handle)

**Files:**
- Modify: `daemon/maez_daemon.py` (injection at lines 4295-4303)
- Test: `tests/test_github_owner_account_provenance.py` (add a class)

Context: `self._last_github_block` is set at line ~7981 from `get_context_block()` (now a `ProvenancedText`). The injection block (4295-4303) must: keep the `if` truthiness check (works via `ProvenancedText.__bool__`), feed the local prompt **plain text** via `.text`, and feed the cycle candidate **plain text** via `.text` (`_extend_cycle_candidates`/`candidates_from_text` call string ops — a raw `ProvenancedText` would break them). The `ProvenancedText` handle stays on `self._last_github_block` for any future cloud-bound assembly. **This is the dual view: `.text` local, the object for egress.**

- [ ] **Step 1: Write the failing test**

Add to `tests/test_github_owner_account_provenance.py`:

```python
class DaemonDualViewTests(unittest.TestCase):
    """The daemon injection must use .text for local paths (string ops) while
    leaving the ProvenancedText handle intact. We assert the source contract:
    the GitHub injection references `.text`, never bare interpolation of the
    ProvenancedText into a place that does string ops."""

    def test_github_injection_uses_text_view_for_local_paths(self):
        import inspect
        from daemon import maez_daemon

        src = inspect.getsource(maez_daemon)
        # Dual view present: both the prompt and the cycle candidate use .text.
        self.assertIn("self._last_github_block.text", src)
        # Old prompt flatten gone: f"...{self._last_github_block}..." (no .text).
        # `{self._last_github_block}` is NOT a substring of
        # `{self._last_github_block.text}`, so this catches only the old line.
        self.assertNotIn("{self._last_github_block}", src)
        # Old raw cycle-candidate arg gone: `self._last_github_block,` (comma) is
        # NOT a substring of `self._last_github_block.text,` (dot), so this
        # catches only the old flatten-risk arg.
        self.assertNotIn("self._last_github_block,", src)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -B -m unittest tests.test_github_owner_account_provenance.DaemonDualViewTests -v`
Expected: FAIL — the source still passes the raw `self._last_github_block` to `_extend_cycle_candidates` and does not reference `.text`.

- [ ] **Step 3: Write minimal implementation**

In `daemon/maez_daemon.py`, replace the GitHub injection block (lines 4295-4303):

```python
        # Add GitHub context if available. Dual view: .text feeds the LOCAL 27B
        # prompt + cycle candidate (string ops); the ProvenancedText handle on
        # self._last_github_block carries owner_account_context to any cloud-bound
        # assembly. owner_account_context is categorically blocked at the cloud
        # egress chokepoint — this material does not leave the body to a cloud model.
        if self._last_github_block:
            prompt += f"\n{self._last_github_block.text}\n"
            _extend_cycle_candidates(
                "fresh_evidence",
                self._last_github_block.text,
                durable_prefix="cycle_github_context",
                salience=65,
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -B -m unittest tests.test_github_owner_account_provenance.DaemonDualViewTests -v`
Expected: PASS.

- [ ] **Step 5: Verify the daemon still imports/compiles (no syntax break in a 9k-line file)**

Run: `.venv/bin/python -B -c "import ast; ast.parse(open('daemon/maez_daemon.py').read()); print('daemon parses OK')"`
Expected: `daemon parses OK`.

- [ ] **Step 6: Commit**

```bash
git add daemon/maez_daemon.py tests/test_github_owner_account_provenance.py
git commit -m "feat(daemon): GitHub block dual-view — .text local, ProvenancedText for egress"
```

---

### Task 4: The canary witness — producer → real proxy → 403 / adapter-not-called

**Files:**
- Test: `tests/test_github_owner_account_provenance.py` (add the integration class)

Context: this is acceptance rule 3, the load-bearing witness. It mirrors `tests/test_subscription_proxy_owner_account_enforcement.py` but **starts from the real producer** (`get_context_block()`), to prove no "tag then flatten": the producer's actual spans drive the real proxy and the door refuses them. The proxy is driven exactly as the existing enforcement test drives it (reload `server` with a temp DB + a fake adapter, build a `maez_egress_segments` bundle from `block.to_wire()`, assert `HTTPException(403)` and the adapter was never called).

- [ ] **Step 1: Write the failing test** (it will actually PASS once Tasks 1-2 are in, because the lock already enforces — this test is the *integration witness* that the producer wires to it; include it as a guard. If you are doing strict TDD, write it before Task 2 and watch it fail at the producer step.)

Add to `tests/test_github_owner_account_provenance.py`:

```python
import importlib
import json
import os
import sqlite3
import tempfile
from unittest import mock

from fastapi import HTTPException

from core.subscription_proxy.adapters.base import CallResult


class _NeverCalledAdapter:
    name = "shadow_test"

    def __init__(self):
        self.prompts = []

    def handles_model(self, model: str) -> bool:
        return model == "shadow-test"

    def health(self) -> dict:
        return {"adapter": self.name, "ok": True}

    async def call(self, *, prompt, system_prompt, model):
        self.prompts.append(prompt)
        return CallResult(reply="must never be produced", model_used=model,
                          input_toks=1, output_toks=1)


class GithubCanaryReachesProxyAndIsRefused(unittest.IsolatedAsyncioTestCase):
    """no tag-then-flatten: the producer's real spans hit the real proxy path
    and the door refuses them (403, adapter not called, content-free)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "proxy.db"
        self._env = mock.patch.dict(os.environ, {
            "MAEZ_SUBSCRIPTION_PROXY_DB": str(self.db_path),
            "MAEZ_EGRESS_TELEMETRY_KEY": "github-canary-test",
        }, clear=False)
        self._env.start()
        from core.subscription_proxy import server
        importlib.reload(server)
        self.server = server
        self.adapter = _NeverCalledAdapter()
        self._adapters = mock.patch.object(server, "ADAPTERS", [self.adapter])
        self._adapters.start()

    def tearDown(self):
        self._adapters.stop()
        self._env.stop()
        self._tmp.cleanup()

    def _github_block_with_canary(self):
        from skills.github_skill import GitHubSkill
        skill = GitHubSkill.__new__(GitHubSkill)
        skill.enabled = True
        skill.username = "CANARY_USER"
        skill._cache = {}
        skill._cache_time = {}
        skill.cache_ttl = 300
        skill.token = "x"
        skill.get_user_repos = lambda: [
            {"name": "GH_CANARY_42", "private": True, "language": "Python",
             "updated_at": "2026-06-01T00:00:00Z", "description": "secret"}
        ]
        skill.get_recent_commits = lambda name, limit=1: []
        skill.get_user_activity = lambda: []
        skill.get_trending_ai_repos = lambda n=5: []
        return skill.get_context_block()   # ProvenancedText(owner_account_context)

    def _proxy_request(self, block):
        from starlette.requests import Request
        body = json.dumps({
            "model": "shadow-test",
            "stream": False,
            "maez_egress_segments": {
                "schema_version": "maez-egress-provenance-v1",
                "parts": {"user": block.to_wire()},   # the producer's real spans
            },
            "messages": [{"role": "user", "content": block.text}],
        }).encode()

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        return Request({
            "type": "http", "method": "POST", "path": "/v1/chat/completions",
            "headers": [(b"x-maez-caller", b"github-canary")],
        }, receive)

    async def test_github_owner_account_canary_is_refused_at_proxy(self):
        block = self._github_block_with_canary()
        # sanity: the producer actually stamped owner_account_context
        self.assertTrue(all(s.origin_class == "owner_account_context" for s in block.spans))
        self.assertIn("GH_CANARY_42", block.text)

        with self.assertRaises(HTTPException) as ctx:
            await self.server.chat_completions(self._proxy_request(block))
        self.assertEqual(ctx.exception.status_code, 403)
        # adapter NEVER called — GitHub owner-account data did not reach the cloud
        self.assertEqual(self.adapter.prompts, [])
        self.assertNotIn("GH_CANARY_42", json.dumps(self.adapter.prompts))

    async def test_block_holds_with_redaction_allowed_and_records_content_free(self):
        block = self._github_block_with_canary()
        try:
            await self.server.chat_completions(self._proxy_request(block))
        except HTTPException:
            pass
        with sqlite3.connect(self.db_path) as con:
            row = con.execute(
                "SELECT egress_decision, egress_reason_codes, egress_shadow_mode, "
                "prompt_preview, egress_origin_classes FROM calls"
            ).fetchone()
        self.assertIsNotNone(row)
        decision, reasons, shadow_mode, prompt_preview, origin_classes = row
        self.assertEqual(decision, "block")
        self.assertIn("owner_account_context_blocked_default", reasons)
        self.assertEqual(shadow_mode, 0)                  # ENFORCED, not shadow
        self.assertIn("owner_account_context", origin_classes)
        self.assertNotIn("GH_CANARY_42", prompt_preview or "")   # content-free
```

- [ ] **Step 2: Run the test**

Run: `.venv/bin/python -B -m unittest tests.test_github_owner_account_provenance.GithubCanaryReachesProxyAndIsRefused -v`
Expected: PASS (the producer stamps; the proxy refuses; adapter never called; telemetry content-free).

> If it FAILS with the adapter being called or status != 403, the producer is not actually emitting `owner_account_context` spans (tag-then-flatten regression) — fix the producer, do not weaken the test.

- [ ] **Step 3: Commit**

```bash
git add tests/test_github_owner_account_provenance.py
git commit -m "test(github): canary witness — producer spans refused at the real proxy (403, no adapter)"
```

---

### Task 5: Verify the live/latent egress path; name the residual diffuse-path gap (acceptance rule 4)

**Files:**
- Modify: `docs/superpowers/specs/2026-06-04-github-limb-v0.1-design.md` (append a "Residual gap — verified" section)

Context: acceptance rule 4 demands honesty about what is **not** closed. The daemon's GitHub paths are local (the 27B); the cycle-candidate → memory → recall path flattens to `.text` (Task 3), so provenance is **not** preserved across that diffuse route. v0.1 closes the producer + proves the door; it does not thread provenance through memory/recall (that is the digestion slice). This task records the verified finding rather than silently implying full closure.

- [ ] **Step 1: Verify whether any *live* path carries GitHub content into a `claude_tier` cloud call today**

Run (read-only investigation — record the output in the commit message):

```bash
cd /home/rohit/maez
# Does anything pass cycle/github/recall content into claude_tier.call/call_messages?
grep -rn "claude_tier" daemon/ core/ | grep -iE "call\(|call_messages\(|recall|cycle|memory" | head
# Does the cycle candidate / memory path carry origin_class, or only text?
grep -rn "candidates_from_text\|def candidates_from" core/ | head
```

Expected finding (confirm or correct): the cycle-candidate path is text-only (`candidates_from_text`), and no daemon code passes a GitHub-derived `ProvenancedText` into `claude_tier`. So the GitHub→cloud route is **latent/diffuse and flattening**, not a live provenance-preserving path.

- [ ] **Step 2: Append the verified residual-gap section to the spec**

Add to `docs/superpowers/specs/2026-06-04-github-limb-v0.1-design.md`:

```markdown

---

## 9. Residual gap — verified at implementation (acceptance rule 4)

**What v0.1 closed:** the producer (`github_skill.get_context_block`) now emits
`ProvenancedText(owner_account_context)`; a canary driven through the real
subscription-proxy path is refused (403, adapter not called, content-free) —
`tests/test_github_owner_account_provenance.py`.

**Named residual gap (deferred to the digestion slice):** the daemon's GitHub
paths are local (the 27B cycle). The cycle-candidate → memory → recall route is
**text-only** (`_cycle_packet.candidates_from_text`), so it **flattens** the
provenance: GitHub content that reaches a cloud-routed query *via recalled
memory* would arrive as untagged text (falling back to `owner_message_context`,
which is not categorically blocked). v0.1 does **not** thread `owner_account_context`
through the memory/recall substrate — that is the digestion slice. This is a
**named, known gap**, not a claim of full closure. Also noted: `owner_account_context`
is absent from `_RESTRICTIVENESS` in `core/egress/provenance.py` (blend scoring
treats it via the `unclassified=4` fallback) — fine for the direct stamp, to be
made explicit in the digestion slice.
```

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-06-04-github-limb-v0.1-design.md
git commit -m "docs(github-limb): name the verified diffuse-path residual gap (acceptance rule 4)"
```

---

### Task 6: Retire the unattended auto-push

**Files:**
- Modify: `daemon/maez_daemon.py` (the publish block inside `_write_journal_entry`, lines 7623-7633)
- Test: `tests/test_github_publish_retired.py` (create)

Context: `_write_journal_entry()` (def at line 7399) currently calls `GitHubPublisher().publish_nightly()` (lines 7623-7633), which does `git push -u origin main` to the public repo. Acceptance rule 5: remove the **unattended** call. `skills/github_publish.py` stays on disk for a future *deliberate* owner-initiated publish; nothing fires it automatically.

- [ ] **Step 1: Write the failing test**

Create `tests/test_github_publish_retired.py`:

```python
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""v0.1: the journal path must NOT perform an unattended GitHub publish / push.
Public exposure is a deliberate owner action, not a cron. Source-contract guard
in the spirit of the existing egress markers."""

from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class JournalDoesNotAutoPublishTests(unittest.TestCase):
    def test_write_journal_entry_does_not_call_publish_nightly(self):
        from daemon.maez_daemon import MaezDaemon

        src = inspect.getsource(MaezDaemon._write_journal_entry)
        self.assertNotIn("publish_nightly", src)
        self.assertNotIn("GitHubPublisher", src)

    def test_daemon_module_has_no_unattended_publish_call(self):
        from daemon import maez_daemon

        src = inspect.getsource(maez_daemon)
        # The publisher class may still be imported for a future deliberate path,
        # but it must never be invoked from the daemon's automatic flow.
        self.assertNotIn("publisher.publish_nightly()", src)
        self.assertNotIn("GitHubPublisher().publish_nightly()", src)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -B -m unittest tests.test_github_publish_retired -v`
Expected: FAIL — `_write_journal_entry` still contains `GitHubPublisher` / `publish_nightly`.

- [ ] **Step 3: Write minimal implementation**

In `daemon/maez_daemon.py`, delete the publish block (lines 7623-7633):

```python
        # Publish to GitHub after journal
        try:
            from skills.github_publish import GitHubPublisher

            publisher = GitHubPublisher()
            if publisher.publish_nightly():
                logger.info("GitHub publish completed after journal")
            else:
                logger.warning("GitHub publish failed")
        except Exception as e:
            logger.error("GitHub publish error: %s", e)
```

Replace it with a comment recording the deliberate retirement:

```python
        # GitHub auto-publish RETIRED (v0.1, 2026-06-04). The nightly
        # `git push origin main` to the public repo shipped all of main
        # unattended — a sovereignty decision that belongs to the owner, not a
        # cron (cf. the manual, daemon-pausing backup ritual). skills/github_publish.py
        # remains for a future *deliberate* owner-initiated publish; nothing here
        # fires it automatically.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -B -m unittest tests.test_github_publish_retired -v`
Expected: PASS.

- [ ] **Step 5: Verify the daemon still parses**

Run: `.venv/bin/python -B -c "import ast; ast.parse(open('daemon/maez_daemon.py').read()); print('daemon parses OK')"`
Expected: `daemon parses OK`.

- [ ] **Step 6: Commit**

```bash
git add daemon/maez_daemon.py tests/test_github_publish_retired.py
git commit -m "feat(daemon): retire unattended GitHub auto-push from the journal path"
```

---

### Task 7: Full-suite regression gate

**Files:** none (verification only)

Context: a recurring lesson in this codebase — schema-pin and source-contract tests only fail under the **full** suite, not scoped modules. Run the whole suite before declaring done.

- [ ] **Step 1: Run the full test suite**

Run: `.venv/bin/python -B -m unittest discover -s tests -v 2>&1 | tail -40`
Expected: the run completes with `OK` (no new failures). The two new test files pass; no existing egress/provenance/daemon/body-view test regresses.

- [ ] **Step 2: If anything fails, fix the root cause (do not weaken a test)**

Investigate any failure with systematic-debugging. In particular, confirm no test asserted the old `str` return type of `get_context_block` or the old GitHub injection line; if one did, update it to the new dual-view contract (that is a real contract change, not a test to delete).

- [ ] **Step 3: Final commit (only if Step 2 required changes)**

```bash
git add -A
git commit -m "test(github-limb): full-suite green for v0.1 boundary honesty"
```

---

## Self-Review

**1. Spec coverage:**
- Acceptance rule 1 (producer) → Tasks 1 + 2. ✓
- Acceptance rule 2 (survival, no flatten) → Task 3 (dual view) + Task 4 (the producer's real spans drive the proxy). ✓
- Acceptance rule 3 (canary witness: 403 / no adapter / reason / redaction_allowed / content-free) → Task 4. ✓
- Acceptance rule 4 (name the residual gap) → Task 5. ✓
- Acceptance rule 5 (retire auto-push) → Task 6. ✓
- "Do NOT modify gate.py" → no task touches it; Task 1 touches `provenance.py` (producer API). ✓
- Full-suite lesson → Task 7. ✓

**2. Placeholder scan:** No "TBD"/"add error handling"/"similar to". Every code step shows complete code. Task 5 Step 1 is a read-only investigation with exact grep commands + the expected finding, and Step 2 supplies the exact text to append. ✓

**3. Type consistency:** `get_context_block` returns `ProvenancedText` everywhere (Task 2); `ProvenancedText.owner_account_context(text, *, source_ref)` signature matches the existing factory style and is used identically in Tasks 1/2/4; `block.text` (str) and `block.to_wire()` (list[dict]) used consistently; `self._last_github_block` is a `ProvenancedText` after Task 2 and consumed via `.text` in Task 3. ✓

**Note for the implementer (verify, don't assume):** Task 4's two tests should pass as soon as Tasks 1-2 land (the lock already enforces). If you practice strict TDD, write Task 4's `test_github_owner_account_canary_is_refused_at_proxy` *before* Task 2 and confirm it fails at the producer step (block is a `str`, `.to_wire()` raises) — that failure proves the witness is wired to the producer, not to a hand-built span.
