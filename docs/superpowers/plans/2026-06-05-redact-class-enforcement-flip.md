# Redact-Class Enforcement Flip Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the subscription proxy forward `decide_egress`'s sanitized result (not the original) for redact-class cloud calls — reconstructing the gate's `sanitized_segments` faithfully into the adapter's `(system_prompt, prompt)` split, fail-closed on reconstruction failure, behind a survey-gated owner-authorized default.

**Architecture:** Modify `core/subscription_proxy/server.py` `chat_completions`: after `decide_egress`, when `decision=="redact"` and `_redact_enforced()`, reconstruct the sanitized `(system_prompt, prompt)` from the gate's per-segment output and forward that to the adapter (`egress_shadow_mode=False`); reconstruction failure → 403, never the original. A `MAEZ_EGRESS_REDACT_SHADOW` kill-switch (default-shadow during rollout, flipped to default-enforce after a content-free survey). Graduate the recall-origin canary.

**Tech Stack:** Python 3.14, `unittest` + `unittest.IsolatedAsyncioTestCase`, `fastapi`/`starlette` (proxy), the egress gate + cloud redactor.

**Spec:** `docs/superpowers/specs/2026-06-05-redact-class-enforcement-flip-design.md`

**⚠️ Behavior-affecting at the cloud chokepoint.** The live behavior change is the **default-on flip (Task 6)** — it carries the `## Predicted effect`. Tasks 1-5 land the capability **default-shadow** (zero live change). Task 6 is **owner-authorized on the survey verdict.** Test runner `.venv/bin/python -B -m unittest`; full `discover`; apples-to-apples in `/home/rohit/maez`. **No restart / no push.**

---

## File Structure

| File | Change |
|------|--------|
| `core/subscription_proxy/server.py` | `_redact_enforced()` + `_REDACT_SHADOW_DEFAULT`; `_build_egress_request` returns per-part segment counts; `_sanitized_forward_payload()` reconstruction (fail-closed); the enforce wiring in `chat_completions`. |
| `scripts/redact_enforcement_survey.py` | The content-free survey (volume + over-redaction + coherence). |
| `tests/test_redact_class_enforcement.py` | The enforce/kill-switch/reconstruction/fail-closed/single-source tests incl. the headline mixed-payload test. |
| `tests/test_recall_origin_egress_canary.py` | Graduate `ProxyRedactClassTests` when default-on lands (Task 6). |

**Reused:** `core/egress/gate.py`, `core/safety/cloud_redactor.py` (`redact_for_cloud`), the proxy test scaffolding from `tests/test_recall_origin_egress_canary.py` / `tests/test_owner_account_memory_taint_rail.py`.

---

## Task 1: `_redact_enforced()` helper (default-shadow + kill-switch)

**Files:**
- Modify: `core/subscription_proxy/server.py`
- Test: `tests/test_redact_class_enforcement.py`

- [ ] **Step 1: Add the helper near `_reserved_denied_enforced` in `server.py`**

```python
# "1" = shadow (forward original). Default-SHADOW during rollout; Task 6 flips
# this to "0" (enforce) after the survey clears. MAEZ_EGRESS_REDACT_SHADOW
# always overrides (kill-switch / opt-in regardless of the default).
_REDACT_SHADOW_DEFAULT = "1"


def _redact_enforced() -> bool:
    return os.environ.get("MAEZ_EGRESS_REDACT_SHADOW", _REDACT_SHADOW_DEFAULT) != "1"
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_redact_class_enforcement.py
from __future__ import annotations

import importlib
import os
import unittest
from unittest import mock


class RedactEnforcedHelperTests(unittest.TestCase):
    def _helper(self):
        from core.subscription_proxy import server
        return server

    def test_default_is_shadow(self):
        server = self._helper()
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MAEZ_EGRESS_REDACT_SHADOW", None)
            # default constant is "1" (shadow) during rollout
            self.assertFalse(server._redact_enforced())

    def test_enforce_opt_in(self):
        server = self._helper()
        with mock.patch.dict(os.environ, {"MAEZ_EGRESS_REDACT_SHADOW": "0"}, clear=False):
            self.assertTrue(server._redact_enforced())

    def test_kill_switch_reverts(self):
        server = self._helper()
        with mock.patch.dict(os.environ, {"MAEZ_EGRESS_REDACT_SHADOW": "1"}, clear=False):
            self.assertFalse(server._redact_enforced())
```

- [ ] **Step 3: Run — verify pass**

Run: `.venv/bin/python -B -m unittest tests.test_redact_class_enforcement.RedactEnforcedHelperTests -v`
Expected: PASS (default shadow; `=0` enforces; `=1` shadow).

- [ ] **Step 4: Commit**

```bash
git add core/subscription_proxy/server.py tests/test_redact_class_enforcement.py
git commit -m "feat(egress): _redact_enforced helper (default-shadow + kill-switch)

Mirrors the reserved-denied pattern: _REDACT_SHADOW_DEFAULT='1' (shadow)
during rollout; MAEZ_EGRESS_REDACT_SHADOW overrides. No call site yet, so no
live behavior change.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Reconstruct the sanitized `(system, prompt)` from the gate's segments

**Files:**
- Modify: `core/subscription_proxy/server.py`
- Test: `tests/test_redact_class_enforcement.py`

This is the **must-prove**. `_build_egress_request` builds segments per rendered part in order; expose the per-part counts so the enforce path can re-group `sanitized_segments` back to parts.

- [ ] **Step 1: Make `_build_egress_request` return per-part segment counts**

Change its return type to `tuple[EgressRequest, str, list[tuple[str, int]]]`. In the span-bundle loop (server.py:513-528), accumulate `part_counts.append((key, len(part_spans)))` after `segments.extend(part_spans)`. Return `[]` from every blocked/legacy-mismatch return, and `[("legacy_prompt", 1)]` from the legacy single-segment return (the `bundle is None` branch). Update the call site (server.py:664) to unpack the third value:

```python
egress_request, egress_provenance_mode, part_counts = _build_egress_request(
    body=body, rendered_parts=rendered_parts, prompt=prompt,
    system_prompt=system_prompt, destination=f"subscription_proxy:{adapter.name}",
    caller=caller, request_id=request_id,
)
```

- [ ] **Step 2: Add `_sanitized_forward_payload`**

```python
def _sanitized_forward_payload(decision, part_counts, *, system_prompt, prompt):
    """Reconstruct (forward_system, forward_prompt) from the gate's
    sanitized_segments. Returns None if it cannot be proven faithful
    (caller fails closed -> 403). Single source of truth: the gate's output,
    never a re-scrub of the flattened prompt."""
    sanitized = list(decision.sanitized_segments or [])
    if not part_counts or sum(count for _key, count in part_counts) != len(sanitized):
        return None
    grouped: dict[str, str] = {}
    idx = 0
    for key, count in part_counts:
        grouped[key] = "".join(sanitized[idx:idx + count])
        idx += count
    if part_counts == [("legacy_prompt", 1)]:
        # Legacy egress gated only the prompt; system was not in the request.
        return system_prompt, grouped["legacy_prompt"]
    forward_system = grouped.get("system", system_prompt)
    forward_prompt = "\n\n".join(
        grouped[key]
        for key in ("assistant_history", "role_history", "user")
        if key in grouped
    ).strip()
    return forward_system, forward_prompt
```

- [ ] **Step 3: Write the failing reconstruction tests (incl. the headline mixed-payload)**

```python
# Append to tests/test_redact_class_enforcement.py
_PRIV = "secret-pii-9a2b@example.test"
_PUB_SYS = "PUBLIC-SYSTEM-MARKER"
_PUB_USER = "PUBLIC-USER-MARKER"


def _decision(sanitized_segments, decision="redact"):
    # A minimal stand-in carrying just what _sanitized_forward_payload reads.
    from types import SimpleNamespace
    return SimpleNamespace(decision=decision, sanitized_segments=list(sanitized_segments))


class SanitizedForwardTests(unittest.TestCase):
    def test_mixed_system_and_user_split_preserved(self):
        # HEADLINE (spec §9.1): system + user each have a public span + a private
        # span; the gate has redacted only the private spans. Reconstruction must
        # keep the split, drop the private markers, keep the public ones.
        from core.subscription_proxy import server
        # segments order: system(2 spans), user(2 spans)
        part_counts = [("system", 2), ("user", 2)]
        sanitized = [
            f"{_PUB_SYS} ", "[REDACTED_EMAIL]",     # system: public kept, private masked
            f"{_PUB_USER} ", "[REDACTED_EMAIL]",    # user:   public kept, private masked
        ]
        fwd_system, fwd_prompt = server._sanitized_forward_payload(
            _decision(sanitized), part_counts,
            system_prompt=f"{_PUB_SYS} {_PRIV}", prompt=f"{_PUB_USER} {_PRIV}",
        )
        # correct split
        self.assertIn(_PUB_SYS, fwd_system)
        self.assertIn(_PUB_USER, fwd_prompt)
        self.assertNotIn(_PUB_USER, fwd_system)   # no smear: user marker not in system
        self.assertNotIn(_PUB_SYS, fwd_prompt)    # no smear: system marker not in prompt
        # private absent from both
        self.assertNotIn(_PRIV, fwd_system)
        self.assertNotIn(_PRIV, fwd_prompt)

    def test_count_mismatch_fails_closed(self):
        from core.subscription_proxy import server
        # 3 segments declared, 2 sanitized -> cannot prove faithful -> None
        result = server._sanitized_forward_payload(
            _decision(["a", "b"]), [("system", 1), ("user", 2)],
            system_prompt="s", prompt="p",
        )
        self.assertIsNone(result)

    def test_legacy_path_sanitizes_prompt_keeps_system(self):
        from core.subscription_proxy import server
        fwd_system, fwd_prompt = server._sanitized_forward_payload(
            _decision(["[REDACTED_EMAIL] tail"]), [("legacy_prompt", 1)],
            system_prompt="orig-system", prompt=f"{_PRIV} tail",
        )
        self.assertEqual(fwd_system, "orig-system")
        self.assertNotIn(_PRIV, fwd_prompt)
```

- [ ] **Step 4: Run — verify pass**

Run: `.venv/bin/python -B -m unittest tests.test_redact_class_enforcement.SanitizedForwardTests -v`
Expected: PASS — especially `test_mixed_system_and_user_split_preserved` (the spine) and `test_count_mismatch_fails_closed`.

- [ ] **Step 5: Confirm `_build_egress_request`'s other callers/tests still pass**

Run: `.venv/bin/python -B -m unittest tests.test_owner_account_memory_taint_rail tests.test_recall_origin_egress_canary -v 2>&1 | tail -4`
Expected: PASS (the third return value is additive; existing proxy drive still works).

- [ ] **Step 6: Commit**

```bash
git add core/subscription_proxy/server.py tests/test_redact_class_enforcement.py
git commit -m "feat(egress): reconstruct sanitized (system,prompt) from gate segments

_build_egress_request returns per-part segment counts; _sanitized_forward_payload
re-groups the gate's sanitized_segments back into the (system_prompt, prompt)
split — single source of truth, fail-closed (None) on count mismatch. Headline
mixed-payload test pins the no-smear / drop-private / keep-public invariant.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Wire the enforce path into `chat_completions` (default-shadow)

**Files:**
- Modify: `core/subscription_proxy/server.py`
- Test: `tests/test_redact_class_enforcement.py`

- [ ] **Step 1: Insert the enforce computation before the adapter call (server.py ~742)**

Just before `result = await adapter.call(...)` (743), compute the forwarded payload; after, thread `egress_shadow_mode` from `enforced_redact` into both `_record` calls (the error path ~759 and the ok path ~779).

```python
        forward_system, forward_prompt = system_prompt, prompt
        enforced_redact = False
        if egress_decision.decision == "redact" and _redact_enforced():
            reconstructed = _sanitized_forward_payload(
                egress_decision, part_counts,
                system_prompt=system_prompt, prompt=prompt,
            )
            if reconstructed is None:
                # FAIL-CLOSED: cannot prove faithful forwarding -> block, never
                # forward the original (spec §4).
                _record(
                    adapter=adapter.name, caller=caller, model=model_in,
                    model_used=None, prompt=prompt, reply="",
                    input_toks=None, output_toks=None,
                    duration_s=0.0, status="blocked_egress",
                    egress_decision=egress_decision.decision,
                    egress_reason_codes=",".join(egress_decision.reason_codes),
                    egress_content_digest=egress_telemetry["content_digest"],
                    egress_shadow_mode=False,
                    egress_origin_classes=",".join(egress_decision.origin_classes),
                    egress_provenance_mode=egress_provenance_mode,
                    prompt_preview_override=prompt_preview,
                    reply_preview_override="",
                )
                raise HTTPException(403, "egress blocked: redact reconstruction failed")
            forward_system, forward_prompt = reconstructed
            enforced_redact = True

        t0 = time.time()
        try:
            result = await adapter.call(
                prompt=forward_prompt, system_prompt=forward_system, model=model_in,
            )
```

Then in BOTH `_record` calls below (error and ok), change `egress_shadow_mode=True` to `egress_shadow_mode=not enforced_redact`.

- [ ] **Step 2: Write the failing enforce/kill-switch/block-class tests**

Reuse the proxy scaffolding pattern from `tests/test_recall_origin_egress_canary.py` (a capturing adapter, `_make_proxy_request`, the reload-server `setUp`). Add to `tests/test_redact_class_enforcement.py`:

```python
# Append to tests/test_redact_class_enforcement.py
import json, sqlite3, tempfile
from contextlib import closing
from pathlib import Path
from starlette.requests import Request
from fastapi import HTTPException
from core.subscription_proxy.adapters.base import CallResult


class _CapturingAdapter:
    name = "redact-enforce-canary"
    def __init__(self): self.prompts = []; self.systems = []
    def handles_model(self, model): return model == "redact-enforce-model"
    def health(self): return {"adapter": self.name, "ok": True}
    async def call(self, *, prompt, system_prompt, model):
        self.prompts.append(prompt); self.systems.append(system_prompt)
        return CallResult(reply="ok", model_used=model, input_toks=1, output_toks=1)


def _wire_span(text, origin_class, *, redaction_allowed):
    # Confirm the exact wire keys against core/egress/provenance.py
    # ProvenanceSpan.to_wire/from_wire before relying on this.
    return {"text": text, "origin_class": origin_class,
            "source_ref": "raw:redact-test", "redaction_allowed": redaction_allowed}


def _mixed_body():
    system_text = f"{_PUB_SYS} {_PRIV}"
    user_text = f"{_PUB_USER} {_PRIV}"
    return {
        "model": "redact-enforce-model",
        "messages": [
            {"role": "system", "content": system_text},
            {"role": "user", "content": user_text},
        ],
        "maez_egress_segments": {
            "destination": "subscription_proxy:redact-enforce-canary",
            "parts": {
                "system": [_wire_span(f"{_PUB_SYS} ", "public_fact", redaction_allowed=False),
                           _wire_span(_PRIV, "third_party_private_context", redaction_allowed=True)],
                "user": [_wire_span(f"{_PUB_USER} ", "public_fact", redaction_allowed=False),
                         _wire_span(_PRIV, "third_party_private_context", redaction_allowed=True)],
            },
        },
    }


class _ProxyBase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "proxy.db"
        self._env = mock.patch.dict(os.environ, {
            "MAEZ_SUBSCRIPTION_PROXY_DB": str(self.db_path),
            "MAEZ_EGRESS_TELEMETRY_KEY": "redact-enforce-test",
            "MAEZ_SECRETS_DISABLE_NEW_LOADER": "1",
            "MAEZ_IPHONE_INGEST_TOKEN": "dummy",
            "MAEZ_EGRESS_REDACT_SHADOW": self.SHADOW,
        }, clear=False)
        self._env.start()
        from core.subscription_proxy import server
        importlib.reload(server)
        self.server = server
        self.adapter = _CapturingAdapter()
        self._adapters = mock.patch.object(server, "ADAPTERS", [self.adapter])
        self._adapters.start()

    def tearDown(self):
        self._adapters.stop(); self._env.stop(); self._tmp.cleanup()

    def _make_request(self, body):
        raw = json.dumps(body).encode("utf-8")
        async def receive(): return {"type": "http.request", "body": raw, "more_body": False}
        return Request({"type": "http", "method": "POST", "path": "/v1/chat/completions",
                        "headers": [(b"x-maez-caller", b"redact-enforce-canary")]}, receive)

    def _row(self):
        with closing(sqlite3.connect(self.db_path)) as con:
            return con.execute("SELECT egress_decision, egress_shadow_mode FROM calls").fetchone()


class EnforceOnTests(_ProxyBase):
    SHADOW = "0"  # enforce
    async def test_redact_forwards_sanitized_split_shadow0(self):
        await self.server.chat_completions(self._make_request(_mixed_body()))
        sys_fwd, prompt_fwd = self.adapter.systems[0], self.adapter.prompts[0]
        self.assertNotIn(_PRIV, sys_fwd)
        self.assertNotIn(_PRIV, prompt_fwd)
        self.assertIn(_PUB_SYS, sys_fwd)
        self.assertIn(_PUB_USER, prompt_fwd)
        self.assertNotIn(_PUB_USER, sys_fwd)
        self.assertNotIn(_PUB_SYS, prompt_fwd)
        decision, shadow = self._row()
        self.assertEqual(decision, "redact")
        self.assertEqual(shadow, 0)


class ShadowKillSwitchTests(_ProxyBase):
    SHADOW = "1"  # kill-switch / shadow
    async def test_redact_forwards_original_shadow1(self):
        await self.server.chat_completions(self._make_request(_mixed_body()))
        self.assertIn(_PRIV, self.adapter.prompts[0])  # original forwarded (shadow)
        decision, shadow = self._row()
        self.assertEqual(decision, "redact")
        self.assertEqual(shadow, 1)
```

- [ ] **Step 3: Run — verify pass**

Run: `.venv/bin/python -B -m unittest tests.test_redact_class_enforcement.EnforceOnTests tests.test_redact_class_enforcement.ShadowKillSwitchTests -v`
Expected: PASS. If the wire-span keys are wrong, `_build_egress_request` will return `span_bundle_invalid` (the byte-validation fails) — confirm the keys against `core/egress/provenance.py` `ProvenanceSpan.from_wire` and that the part text equals the message content byte-exactly.

- [ ] **Step 4: Confirm block-class still enforced + existing egress suite green**

Run: `.venv/bin/python -B -m unittest tests.test_recall_origin_egress_canary.ProxyBlockClassTests tests.test_egress_owner_account_firewall tests.test_privacy_egress_gate -v 2>&1 | tail -4`
Expected: PASS (owner-account still 403; the change is scoped to the redact branch).

- [ ] **Step 5: Commit**

```bash
git add core/subscription_proxy/server.py tests/test_redact_class_enforcement.py
git commit -m "feat(egress): redact-class enforce path in chat_completions (default-shadow)

When decision=redact and _redact_enforced(), forward the gate's reconstructed
sanitized (system,prompt) to the adapter (egress_shadow_mode=0); reconstruction
failure fails closed to 403, never the original. Default-shadow, so no live
behavior change yet. Kill-switch + enforce both tested; block-class unchanged.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: The content-free survey

**Files:**
- Create: `scripts/redact_enforcement_survey.py`
- Test: `tests/test_redact_class_enforcement.py`

- [ ] **Step 1: Write the survey**

```python
# scripts/redact_enforcement_survey.py
"""Content-free survey gating the redact-class default-on. Emits counts +
ratios + a coherence flag ONLY — never content. See the spec §5."""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing


_PROSE = (
    "We reviewed the recall plan this morning and agreed the temporal slice "
    "lands before the embodiment work; notes captured in the usual place."
)
_PII_DENSE = (
    "contacts: a@x.test b@y.test c@z.test phones 555-0101 555-0102 555-0103 "
    "keys sk-aaaa1111 sk-bbbb2222 path /home/owner/secret.txt"
)
_MIXED = f"PUBLIC-CONTEXT-OK reach me at owner@x.test and 555-0199 then continue."


def _impact(text: str) -> dict:
    from core.safety.cloud_redactor import redact_for_cloud
    result = redact_for_cloud(text)
    original = len(text)
    masked = max(0, original - len(result.text))
    ratio = (masked / original) if original else 0.0
    stripped = result.text.strip()
    near_empty = len(stripped) < max(8, int(0.15 * original))
    return {
        "masking_ratio": round(ratio, 4),
        "pii_counts": dict(getattr(result, "pii_counts", {}) or {}),
        "near_empty": bool(near_empty),
    }


def survey(db_path: str | None = None) -> dict:
    volume = None
    if db_path:
        try:
            with closing(sqlite3.connect(db_path)) as con:
                volume = con.execute(
                    "SELECT COUNT(*) FROM calls WHERE egress_decision='redact'"
                ).fetchone()[0]
        except sqlite3.Error:
            volume = None
    prose, dense, mixed = _impact(_PROSE), _impact(_PII_DENSE), _impact(_MIXED)
    # Provisional NO-GO logic (spec §5): prose>25% OR any near-empty.
    no_go = (prose["masking_ratio"] > 0.25) or prose["near_empty"] or mixed["near_empty"]
    return {
        "schema": "redact_enforcement_survey.v1",
        "redact_volume": volume,
        "prose": prose, "pii_dense": dense, "mixed": mixed,
        "provisional_verdict": "NO_GO" if no_go else "CLEAN",
    }


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--db", default=None)
    args = p.parse_args()
    print(json.dumps(survey(args.db), indent=2, sort_keys=True))
```

- [ ] **Step 2: Write the failing survey test (content-free)**

```python
# Append to tests/test_redact_class_enforcement.py
class SurveyTests(unittest.TestCase):
    def test_survey_is_content_free_and_structured(self):
        from scripts.redact_enforcement_survey import survey
        out = survey(db_path=None)
        blob = json.dumps(out)
        # content-free: no raw sample content / PII in the output
        for fragment in ("owner@x.test", "sk-aaaa1111", "secret.txt", "555-0101"):
            self.assertNotIn(fragment, blob)
        self.assertIn(out["provisional_verdict"], ("CLEAN", "NO_GO"))
        self.assertIn("masking_ratio", out["prose"])
        self.assertIn("near_empty", out["prose"])

    def test_prose_masks_lightly(self):
        from scripts.redact_enforcement_survey import survey
        out = survey(db_path=None)
        # prose memory should mask lightly (it's the readability of enforce-on)
        self.assertLessEqual(out["prose"]["masking_ratio"], 0.25, out["prose"])
        self.assertFalse(out["prose"]["near_empty"])
```

- [ ] **Step 3: Run — verify pass + eyeball the numbers**

Run: `.venv/bin/python -B -m unittest tests.test_redact_class_enforcement.SurveyTests -v` then `.venv/bin/python -B -m scripts.redact_enforcement_survey`
Expected: PASS; the printed survey shows prose masking lightly, PII-dense heavily, mixed preserving `PUBLIC-CONTEXT-OK`. **If prose masks >25%, that's the real NO-GO signal — surface it to the owner, do not tune the redactor here.**

- [ ] **Step 4: Commit**

```bash
git add scripts/redact_enforcement_survey.py tests/test_redact_class_enforcement.py
git commit -m "feat(egress): content-free redact-enforcement survey

Volume (redact-class call count from the proxy DB) + over-redaction (masking
ratio + pii_counts + near_empty coherence flag) on representative prose/
PII-dense/mixed shapes via redact_for_cloud. Provisional verdict; owner reads
the real numbers. Content-free (counts/ratios only).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Run the survey + report the verdict (owner reads it)

**Files:** none (verification + report)

- [ ] **Step 1: Run the survey against the live proxy DB (read-only) + the synthetic shapes**

Run: `.venv/bin/python -B -m scripts.redact_enforcement_survey --db "$(python -c "import os;print(os.environ.get('MAEZ_SUBSCRIPTION_PROXY_DB',''))")" 2>/dev/null || .venv/bin/python -B -m scripts.redact_enforcement_survey`
Expected: a content-free JSON verdict. Record `provisional_verdict`, the prose/mixed ratios, and whether any `near_empty` is true.

- [ ] **Step 2: Report to the owner**

Present the survey JSON. The owner authorizes Task 6 (default-on flip) only on a CLEAN verdict (prose ≤ 25%, no near-empty, mixed preserves public). If NO_GO, STOP — Task 6 becomes a named follow-up after the over-redaction is addressed; the slice lands default-shadow.

---

## Task 6: (Owner-authorized) flip default-on + graduate the canary — `## Predicted effect`

**Files:**
- Modify: `core/subscription_proxy/server.py`
- Modify: `tests/test_recall_origin_egress_canary.py`

**Only run this task after the owner authorizes on a CLEAN survey verdict (Task 5).**

- [ ] **Step 1: Flip the default to enforce**

In `core/subscription_proxy/server.py`, change `_REDACT_SHADOW_DEFAULT = "1"` to `_REDACT_SHADOW_DEFAULT = "0"`. The kill-switch (`MAEZ_EGRESS_REDACT_SHADOW=1`) is retained.

- [ ] **Step 2: Graduate the recall-origin canary's redact-class test**

The tripwire fires (the canary's `ProxyRedactClassTests` asserts `egress_shadow_mode=1` + adapter-got-PII, which is now false). Update it in `tests/test_recall_origin_egress_canary.py`:

```python
        # GRADUATED (redact-class enforcement flip landed): forwarding is now
        # enforced — the adapter receives the sanitized prompt.
        self.assertEqual(decision, "redact")
        self.assertNotIn(_PII_MARKER, prompt_preview or "")
        self.assertIn("third_party_private_context", origins)
        self.assertEqual(shadow_mode, 0)
        self.assertEqual(len(self.adapter.prompts), 1)
        self.assertNotIn(_PII_MARKER, self.adapter.prompts[0])  # adapter now PII-free
```

- [ ] **Step 3: Run the affected suites — verify green**

Run: `.venv/bin/python -B -m unittest tests.test_redact_class_enforcement tests.test_recall_origin_egress_canary -v 2>&1 | tail -6`
Expected: PASS (enforce now default; canary graduated).

- [ ] **Step 4: Commit (carries `## Predicted effect`)**

```bash
git add core/subscription_proxy/server.py tests/test_recall_origin_egress_canary.py
git commit -m "feat(egress): flip redact-class to enforce-default + graduate canary

The door now forwards the gate's sanitized result for redact-class cloud
calls (default-on; MAEZ_EGRESS_REDACT_SHADOW=1 reverts). Recall-origin canary
graduated shadow->enforced (adapter now PII-free for redact-class).

## Predicted effect
The cloud model receives PII-masked private-origin content instead of raw
(emails/phones/keys/paths masked; surrounding non-private content preserved).
Light touch for prose memory, heavier for PII-dense. owner-bridge answers may
reference masked placeholders where PII was present. Block-class unchanged.
egress_shadow_mode flips 1->0 for redact-class. Falsifiable: a redact-class
owner-bridge call's adapter payload carries no raw PII marker while keeping the
surrounding non-private content; survey prose masking stays <25%.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: Full-suite green + apples-to-apples

**Files:** none

- [ ] **Step 1: Run the new module + the egress family**

Run: `.venv/bin/python -B -m unittest tests.test_redact_class_enforcement tests.test_recall_origin_egress_canary tests.test_owner_account_memory_taint_rail tests.test_privacy_egress_gate 2>&1 | tail -4`
Expected: ALL PASS.

- [ ] **Step 2: Full discover**

Run: `.venv/bin/python -B -m unittest discover -s tests 2>&1 | tail -6`
Expected: zero new failures attributable to this slice; run in `/home/rohit/maez`. Live-judge flaky floor wobbles ±1-2.

- [ ] **Step 3: Confirm scope + no restart**

`git diff --stat main..HEAD` shows only `server.py`, the new test file, the survey, and the canary update. The live daemon is not restarted (owner decides the live flip posture).

---

## Self-Review (against the spec)

**Spec coverage:**
- §2 must-prove (forward `sanitized_segments`, not re-scrub) → Task 2 `_sanitized_forward_payload` + test `test_mixed_system_and_user_split_preserved`. ✓
- §2 reconstruction preserves split + NON_PRIVATE spans → headline test (no-smear + keep-public). ✓
- §4 fail-closed 403 → Task 2 `test_count_mismatch_fails_closed` + Task 3 fail-closed branch. ✓
- §4 `_redact_enforced` + kill-switch + `egress_shadow_mode` → Task 1 + Task 3 (EnforceOn/ShadowKillSwitch). ✓
- §5 survey content-free + thresholds + coherence flag → Task 4. ✓
- §6 conditional owner-authorized default-on → Task 5 (report) + Task 6 (flip, owner-gated). ✓
- §7 canary graduation → Task 6 Step 2. ✓
- §8 `## Predicted effect` → Task 6 Step 4 commit. ✓
- §9.6 block-class unchanged → Task 3 Step 4. ✓

**Placeholder scan:** none. Two bounded implementer-confirms (the exact `ProvenanceSpan` wire-span keys in Task 3; the live proxy DB path in Task 5) are flagged with the source to check — not placeholders.

**Type consistency:** `_redact_enforced`, `_REDACT_SHADOW_DEFAULT`, `_sanitized_forward_payload(decision, part_counts, *, system_prompt, prompt)`, `_build_egress_request` returning the 3-tuple, `part_counts: list[tuple[str,int]]`, `egress_shadow_mode = not enforced_redact` — consistent across Tasks 1-3. The survey's `survey()`/`_impact()` keys match the test. ✓

**Sequencing note for the implementer:** Tasks 1-5 are safe to land (default-shadow = zero live change). **Task 6 is gated on the owner's CLEAN survey verdict** — do not flip the default or graduate the canary until authorized. If NO_GO, stop after Task 5 and report; the canary stays un-graduated and the flip becomes a follow-up.
