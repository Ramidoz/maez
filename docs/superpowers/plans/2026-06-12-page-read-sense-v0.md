# Page-Read Sense v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wake the dormant `FETCH_URL` limb — owner-named URLs get fetched (egress-witnessed), digested to readable text (stdlib), spoken in voice, and remembered as one bounded observation — behind `MAEZ_PAGE_READ_ENABLED`, default-OFF.

**Architecture:** The FETCH_URL adapter + covenant preflights already exist and are registered; what's missing is the nerve (a flag-gated Layer0 arm for explicit URLs), the digestion (raw HTML currently passes straight into evidence), the content-type guard (a new `ExternalFetchResult.content_type` field), and the stomach (the world-observation lane is WEB_SEARCH-only and its write gate checks only the search-sense flag — the load-bearing OR-gate fix).

**Tech Stack:** Python stdlib only (`html.parser` — no extraction libs are installed, verified). Existing organs: `external_fetch` (egress witness), the dispatcher fanout, the world-observation lane, `attribution_render` stash, unittest + ruff.

**Spec:** `docs/superpowers/specs/2026-06-12-page-read-sense-v0-design.md` (@0a653aa). Read it once first — S1/S2/S3 and the OR-gate are load-bearing.

---

## Ground Rules

- Branch `page-read-sense-v0` off main (@0a653aa). main is local-only — NO `git push`.
- STOP at the gate: no merge, no restart, no flag flips, no service changes.
- Default-OFF: `MAEZ_PAGE_READ_ENABLED` unset ⇒ byte-identical behavior on every seam.
- `## Predicted effect` only on behavior-affecting commits (Tasks 4, 5, 6, 7).
- Co-author trailer on every commit: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
- Tests use fakes only — never a live fetch; mock `external_fetch.fetch_text`.
- These tests must stay green UNTOUCHED: the FETCH_URL preflight tests
  (MODEL_INVENTED_URL, sensitive-query, subject-boundary), all existing
  WEB_SEARCH lane tests, all existing `external_fetch` tests.
- Test runner: `/home/rohit/maez/.venv/bin/python -B -m unittest` (never pytest, never full-discover).

## File Map

| Path | Responsibility |
|---|---|
| `core/search/sense_flag.py` (modify) | + `page_read_enabled()` (the sense-family flag home). |
| `core/egress/external_fetch.py` (modify) | `ExternalFetchResult.content_type` (additive, default "") populated from the response header. |
| `core/search/page_extract.py` (create) | stdlib HTML→text extractor + `extract_first_url()` (the ONE URL regex both Layer0 and the stash use). |
| `core/dispatcher/external_sources.py` (modify) | `_fetch_url_adapter`: content-type guard + extraction between fetch and payload. |
| `core/dispatcher/layer0.py` (modify) | The explicit-URL arm (flag-gated), ABOVE the current-world arm. |
| `core/intake_bus/world_observation_lane.py` (modify) | OR-gate; source-aware condition; `write_page_observation()`. |
| `core/brain/brain_loop.py` (modify) | Stash block handles FETCH_URL branches; source-aware progress wording. |
| `daemon/maez_daemon.py` (modify) | The drain dispatches on `observation["kind"]`. |
| `tests/test_page_extract.py` (create) | Extractor + URL helper. |
| `tests/test_dispatcher_external_sources.py` (modify) | Adapter guard/extraction tests. |
| `tests/test_dispatcher_layer0.py` (modify) | The URL arm + flag matrix. |
| `tests/test_world_observation_lane.py` (modify) | OR-gate matrix + page observation. |
| `tests/test_egress_external_fetch_substrate.py` (modify) | content_type population. |
| `docs/handoffs/2026-06-12-page-read-gate.md` (create) | STOP-at-gate handoff. |

---

### Task 0: Prove the seams (NO feature code until all proofs pass)

This week this discipline caught a dead surface, a wrong nerve, and a
born-refused observation. Record every output for the handoff.

- [ ] **Step 0a: FETCH_URL adapter + preflights**

```bash
cd /home/rohit/maez
grep -n "_fetch_url_adapter\|FETCH_URL" core/dispatcher/external_sources.py | head -8
sed -n '373,410p' core/dispatcher/external_sources.py
sed -n '678,700p' core/dispatcher/external_sources.py
grep -n "_payload_from_fetch_result" core/dispatcher/external_sources.py | head -3
```
Expected: the preflight block (`_extract_urls`, MODEL_INVENTED_URL,
`_has_sensitive_query`) near :373-400; `_fetch_url_adapter` near :678
(fetch via `external_fetch.fetch_text(fetch_type="fetch_url", ...)` then
straight to `_payload_from_fetch_result` — NO extraction, NO content-type
guard: those are this plan's Task 4); registration in `_DEFAULT_ADAPTERS`
(~:715). Record the worktree line numbers. **STOP if** the adapter shape
differs materially.

- [ ] **Step 0b: content_type threading path**

```bash
grep -n "class ExternalFetchResult" -A14 core/egress/external_fetch.py
grep -n "ExternalFetchResult(" core/egress/external_fetch.py
sed -n '395,415p' core/egress/external_fetch.py
```
Expected: the dataclass (:169 region) with NO `content_type`; exactly ONE
success-path construction site (~:257); a header-reading helper near :403
(`getheader`/`headers` access) proving the response headers are in scope
where the result is built. Record the construction line and the helper name.

- [ ] **Step 0c: lane gate + stash + drain**

```bash
grep -n "sense_enabled\|def evaluate_write_condition\|def write_world_observation\|WORLD_OBSERVATION_EGRESS" core/intake_bus/world_observation_lane.py
sed -n '20,30p' core/intake_bus/admit.py
grep -n "stash_turn_evidence\|WEB_SEARCH" core/brain/brain_loop.py | head -8
grep -n "write_world_observation\|pop_turn_evidence" daemon/maez_daemon.py | head -4
```
Expected: the lane gate `if not sense_enabled(): return "disabled"` (~:106);
`WORLD_OBSERVATION_EGRESS = "tool_result_public"`; `_validate` refusing
`unclassified` + non-`KNOWN_ORIGINS` (admit.py:24-26); the WEB_SEARCH-only
stash block in brain_loop (~:878-900); the daemon drain calling
`write_world_observation(self.memory, **_turn_ev["observation"])` (~:6790
region). Record all line numbers.

- [ ] **Step 0d: branch**

```bash
git checkout -b page-read-sense-v0
```

---

### Task 1: The flag

**Files:** Modify `core/search/sense_flag.py`; test `tests/test_page_extract.py` (created here, extended in Task 2).

- [ ] **Step 1: Failing test** — create `tests/test_page_extract.py`:

```python
from __future__ import annotations

import os
import unittest


class PageReadFlagTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("MAEZ_PAGE_READ_ENABLED", None)
        self.addCleanup(lambda: os.environ.pop("MAEZ_PAGE_READ_ENABLED", None))

    def test_default_off(self):
        from core.search.sense_flag import page_read_enabled

        self.assertFalse(page_read_enabled())

    def test_on_when_set(self):
        from core.search.sense_flag import page_read_enabled

        os.environ["MAEZ_PAGE_READ_ENABLED"] = "1"
        self.assertTrue(page_read_enabled())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: RED** — `cd /home/rohit/maez && .venv/bin/python -B -m unittest tests.test_page_extract -v` → ImportError.

- [ ] **Step 3: Implement** — append to `core/search/sense_flag.py`:

```python
def page_read_enabled() -> bool:
    """Page-Read Sense v0 (spec 2026-06-12). Own flag, own witness, own revert."""
    return bool(os.environ.get("MAEZ_PAGE_READ_ENABLED"))
```

- [ ] **Step 4: GREEN** — same command → PASS.
- [ ] **Step 5: Commit**

```bash
git add core/search/sense_flag.py tests/test_page_extract.py
git commit -m "feat(page-read): MAEZ_PAGE_READ_ENABLED flag, default off

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: `ExternalFetchResult.content_type` (spec S1)

**Files:** Modify `core/egress/external_fetch.py`; test `tests/test_egress_external_fetch_substrate.py`.

- [ ] **Step 1: Failing test** — append to `tests/test_egress_external_fetch_substrate.py` (mirror its existing fixture style for faking a response object; the response fake must answer `getheader("Content-Type")`):

```python
class ContentTypeTests(unittest.TestCase):
    def test_result_carries_content_type_default_empty(self):
        from core.egress.external_fetch import ExternalFetchResult

        r = ExternalFetchResult(ok=False)
        self.assertEqual(r.content_type, "")

    def test_success_path_populates_content_type_from_header(self):
        # Drive the module's success construction with a fake response whose
        # Content-Type header is set; reuse this file's existing fetch-path
        # fixture (the same one that fakes status/body) and assert:
        #   result.content_type == "text/html; charset=utf-8"
        # Anchor: the header helper near external_fetch.py:403 and the single
        # success-path ExternalFetchResult(...) construction (~:257, re-check
        # the 0b-recorded line). If this file has no reusable fetch-path
        # fixture, build the minimal fake response object here (getheader +
        # read + status attributes copied from the module's expectations).
        ...
```

Replace the `...` with the working assertion using the file's actual
fixture — the test body must be complete before RED (the existing 32-line
test file shows the response-fake shape; copy it).

- [ ] **Step 2: RED** — `.venv/bin/python -B -m unittest tests.test_egress_external_fetch_substrate -v` → AttributeError `content_type`.

- [ ] **Step 3: Implement** — in `core/egress/external_fetch.py`:
  - add the field to the dataclass (after `response_bytes: int = 0`):

```python
    content_type: str = ""
```

  - at the 0b-recorded success construction site (~:257), read the header
    with the module's existing helper (the `getheader`/`headers` accessor
    near :403) and pass it:

```python
        content_type=str(_header_value(response, "Content-Type") or ""),
```

    (Use the helper's REAL name from 0b; if the helper takes different
    args, match it. Error/refusal constructions stay untouched — the
    default covers them.)

- [ ] **Step 4: GREEN** — same command + `tests.test_searxng_client` (its fetches build the same result type) → PASS.
- [ ] **Step 5: Commit**

```bash
git add core/egress/external_fetch.py tests/test_egress_external_fetch_substrate.py
git commit -m "feat(egress): ExternalFetchResult carries response content_type

Additive (default \"\") — every existing construction and test unchanged.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: The extractor (spec digestion)

**Files:** Create `core/search/page_extract.py`; test `tests/test_page_extract.py`.

- [ ] **Step 1: Failing tests** — append to `tests/test_page_extract.py`:

```python
class ExtractTests(unittest.TestCase):
    def test_strips_boilerplate_and_captures_title(self):
        from core.search.page_extract import extract_readable

        html = (
            "<html><head><title>Releases - llama.cpp</title>"
            "<style>body{color:red}</style><script>var x=1;</script></head>"
            "<body><nav>Home | About</nav><header>Top</header>"
            "<p>b9601 was released on June 11.</p>"
            "<footer>(c) footer</footer><svg><path d='M0'/></svg></body></html>"
        )
        title, text = extract_readable(html, content_type="text/html")
        self.assertEqual(title, "Releases - llama.cpp")
        self.assertIn("b9601 was released", text)
        for noise in ("var x=1", "color:red", "Home | About", "(c) footer", "M0"):
            self.assertNotIn(noise, text)

    def test_plain_text_passthrough_bounded(self):
        from core.search.page_extract import extract_readable

        title, text = extract_readable("x" * 9000, content_type="text/plain")
        self.assertEqual(title, "")
        self.assertEqual(len(text), 6000)

    def test_html_output_bounded(self):
        from core.search.page_extract import extract_readable

        html = "<html><body><p>" + ("word " * 3000) + "</p></body></html>"
        _, text = extract_readable(html, content_type="text/html")
        self.assertLessEqual(len(text), 6000)

    def test_garbage_and_empty_fail_safe(self):
        from core.search.page_extract import extract_readable

        self.assertEqual(extract_readable("", content_type="text/html"), ("", ""))
        self.assertEqual(extract_readable("<<<>>>", content_type="text/html")[1], "")

    def test_extract_first_url(self):
        from core.search.page_extract import extract_first_url

        self.assertEqual(
            extract_first_url("check https://github.com/x/releases please"),
            "https://github.com/x/releases",
        )
        self.assertIsNone(extract_first_url("no links here"))
        self.assertIsNone(extract_first_url("ftp://nope.example/file"))
```

- [ ] **Step 2: RED** — `.venv/bin/python -B -m unittest tests.test_page_extract -v` → ImportError.

- [ ] **Step 3: Implement** — create `core/search/page_extract.py`:

```python
"""Page digestion for the Page-Read Sense (spec 2026-06-12).

stdlib only (no extraction libraries are installed — verified). Quality
bar: honest bounded text, not beauty. Garbage in -> empty out; the caller
maps empty to an honest EMPTY failure, never fake page content.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser

MAX_EXTRACT_CHARS = 6000
_SKIP_SUBTREES = frozenset({"script", "style", "noscript", "nav", "header", "footer", "svg"})
_URL_RE = re.compile(r"https?://[^\s<>\"\')\]]+", re.IGNORECASE)


def extract_first_url(text: str) -> str | None:
    """The ONE owner-URL notion shared by the Layer0 arm and the stash."""
    m = _URL_RE.search(text or "")
    return m.group(0) if m else None


class _ReadableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._in_title = False
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_SUBTREES:
            self._skip_depth += 1
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag in _SKIP_SUBTREES and self._skip_depth > 0:
            self._skip_depth -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title_parts.append(data)
        elif self._skip_depth == 0:
            self.text_parts.append(data)


def extract_readable(raw: str, *, content_type: str) -> tuple[str, str]:
    """Return (title, bounded_text). Empty strings on anything unreadable."""
    try:
        if not raw or not raw.strip():
            return "", ""
        base_type = (content_type or "").split(";", 1)[0].strip().lower()
        if base_type == "text/plain":
            return "", " ".join(raw.split())[:MAX_EXTRACT_CHARS]
        parser = _ReadableParser()
        parser.feed(raw)
        parser.close()
        title = " ".join("".join(parser.title_parts).split())[:200]
        text = " ".join("".join(parser.text_parts).split())[:MAX_EXTRACT_CHARS]
        return title, text
    except Exception:
        return "", ""
```

- [ ] **Step 4: GREEN** — same command → PASS.
- [ ] **Step 5: Commit**

```bash
git add core/search/page_extract.py tests/test_page_extract.py
git commit -m "feat(page-read): stdlib readable-text extractor + shared URL notion

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: The adapter — content-type guard + digestion (spec S1 + digestion)

**Files:** Modify `core/dispatcher/external_sources.py` (`_fetch_url_adapter`, 0a-recorded line); test `tests/test_dispatcher_external_sources.py`.

- [ ] **Step 1: Failing tests** — append to `tests/test_dispatcher_external_sources.py` (mirror its existing adapter-test fixtures; the fetch is mocked with a fake carrying the Task-2 field):

```python
class FetchUrlAdapterTests(unittest.TestCase):
    def _fetched(self, *, text, content_type, ok=True):
        from core.egress.external_fetch import ExternalFetchResult

        return ExternalFetchResult(
            ok=ok, text=text, fetch_type="fetch_url",
            decision="allow", request_id="diag-page-1",
            content_type=content_type,
        )

    def _request(self, utterance):
        from core.dispatcher.external_sources import ExternalAdapterRequest
        from core.dispatcher.spec import ExternalSource

        return ExternalAdapterRequest(
            source=ExternalSource.FETCH_URL,
            utterance=utterance,
            conversation_state={},
            retrieval_timestamp="2026-06-12T00:00:00Z",
        )
        # If ExternalAdapterRequest has more required fields, copy the
        # construction from this file's existing adapter tests verbatim.

    def test_html_is_extracted_not_raw(self):
        from unittest import mock

        from core.dispatcher import external_sources as es

        html = "<html><head><title>T</title><script>x</script></head><body><p>real body text</p></body></html>"
        with mock.patch.object(es.external_fetch, "fetch_text", return_value=self._fetched(text=html, content_type="text/html; charset=utf-8")):
            payload = es._fetch_url_adapter(es.ExternalSource.FETCH_URL, self._request("check https://a.example/page"))
        self.assertIn("real body text", payload.text)
        self.assertIn("T", payload.text.splitlines()[0])
        self.assertNotIn("<script>", payload.text)
        self.assertNotIn("<html>", payload.text)
        self.assertEqual(payload.egress_diagnostic_id, "diag-page-1")

    def test_non_text_content_type_refused_empty(self):
        from unittest import mock

        from core.dispatcher import external_sources as es

        with mock.patch.object(es.external_fetch, "fetch_text", return_value=self._fetched(text="%PDF-1.7 ...", content_type="application/pdf")):
            with self.assertRaises(es._MappedExternalFailure) as ctx:
                es._fetch_url_adapter(es.ExternalSource.FETCH_URL, self._request("check https://a.example/file.pdf"))
        self.assertEqual(ctx.exception.status, es.ExternalBranchStatus.EMPTY)

    def test_empty_extraction_refused_empty(self):
        from unittest import mock

        from core.dispatcher import external_sources as es

        with mock.patch.object(es.external_fetch, "fetch_text", return_value=self._fetched(text="<html><script>only noise</script></html>", content_type="text/html")):
            with self.assertRaises(es._MappedExternalFailure):
                es._fetch_url_adapter(es.ExternalSource.FETCH_URL, self._request("check https://a.example/empty"))
```

- [ ] **Step 2: RED** — `.venv/bin/python -B -m unittest tests.test_dispatcher_external_sources -v` → the new tests FAIL (raw HTML passes through today).

- [ ] **Step 3: Implement** — replace `_fetch_url_adapter`'s body (0a line) with:

```python
def _fetch_url_adapter(
    _source: ExternalSource,
    request: ExternalAdapterRequest,
) -> ExternalAdapterPayload:
    from core.search.page_extract import extract_readable

    url = _extract_urls(request.utterance)[0]
    fetched = external_fetch.fetch_text(
        fetch_type="fetch_url",
        url=url,
        caller="core.dispatcher.external_sources.fetch_url",
        timeout_s=5.0,
    )
    if getattr(fetched, "ok", False):
        # Page-Read v0 (spec S1): only text content becomes evidence; the
        # digestion happens HERE so raw HTML never reaches the prompt.
        base_type = (getattr(fetched, "content_type", "") or "").split(";", 1)[0].strip().lower()
        if base_type not in {"text/html", "text/plain", ""}:
            raise _MappedExternalFailure(
                status=ExternalBranchStatus.EMPTY,
                empty_reason=ExternalEmptyReason.NO_RESULTS,
                limitation=AvailabilityLimitation.FRESH_ATTEMPT_FAILED,
            )
        title, text = extract_readable(fetched.text, content_type=base_type or "text/html")
        if not text.strip():
            raise _MappedExternalFailure(
                status=ExternalBranchStatus.EMPTY,
                empty_reason=ExternalEmptyReason.NO_RESULTS,
                limitation=AvailabilityLimitation.FRESH_ATTEMPT_FAILED,
            )
        return ExternalAdapterPayload(
            text=(title + "\n" + text) if title else text,
            egress_diagnostic_id=str(getattr(fetched, "request_id", "")),
            retrieval_timestamp=request.retrieval_timestamp,
        )
    return _payload_from_fetch_result(
        fetched,
        retrieval_timestamp=request.retrieval_timestamp,
    )
```

(The not-ok path keeps `_payload_from_fetch_result`'s existing typed-failure
mapping untouched. The empty `""` content-type tolerance covers servers that
omit the header — extraction still bounds it.)

- [ ] **Step 4: GREEN + rails untouched** —
`.venv/bin/python -B -m unittest tests.test_dispatcher_external_sources -v` → PASS, including every pre-existing preflight test unmodified.
- [ ] **Step 5: Commit (behavior-affecting)**

```bash
git add core/dispatcher/external_sources.py tests/test_dispatcher_external_sources.py
git commit -m "feat(page-read): digest fetched pages — text-only guard + stdlib extraction

## Predicted effect
FETCH_URL branches (currently never selected by Layer0 — the nerve lands
next) now emit readable title+text instead of raw HTML, refuse non-text
content types as honest EMPTY, and keep the egress-receipt flow unchanged.
No live behavior change until the Layer0 arm + flag exist.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: The nerve — Layer0 explicit-URL arm (flag-gated)

**Files:** Modify `core/dispatcher/layer0.py`; test `tests/test_dispatcher_layer0.py`.

- [ ] **Step 1: Failing tests** — append to `tests/test_dispatcher_layer0.py`, copying the construction pattern of `test_current_world_question_selects_web_search_hybrid` (:190) verbatim for the dispatcher/inventory fixtures:

```python
    def test_owner_url_selects_fetch_url_hybrid_under_flag(self):
        os.environ["MAEZ_PAGE_READ_ENABLED"] = "1"
        self.addCleanup(lambda: os.environ.pop("MAEZ_PAGE_READ_ENABLED", None))
        # fixture setup copied from test_current_world_question_selects_web_search_hybrid
        spec = dispatcher.emit_spec(
            "check https://github.com/ggml-org/llama.cpp/releases - what's the latest release?",
            surface="telegram_surface", inventory=inventory,
        )
        self.assertEqual(spec.external_sources, [ExternalSource.FETCH_URL])  # NOT WEB_SEARCH — URL wins precedence

    def test_owner_url_flag_off_prior_composition(self):
        os.environ.pop("MAEZ_PAGE_READ_ENABLED", None)
        spec = dispatcher.emit_spec(
            "check https://github.com/x/releases please",
            surface="telegram_surface", inventory=inventory,
        )
        self.assertNotIn(ExternalSource.FETCH_URL, spec.external_sources)

    def test_no_url_arm_inert_even_with_flag(self):
        os.environ["MAEZ_PAGE_READ_ENABLED"] = "1"
        self.addCleanup(lambda: os.environ.pop("MAEZ_PAGE_READ_ENABLED", None))
        spec = dispatcher.emit_spec(
            "check that page we talked about",
            surface="telegram_surface", inventory=inventory,
        )
        self.assertNotIn(ExternalSource.FETCH_URL, spec.external_sources)
```

(Adapt fixture variable names to the file's reality; never weaken the three
assertions. The first test's utterance deliberately contains "latest" — the
current-world marker — to pin URL-over-search precedence.)

- [ ] **Step 2: RED** — `.venv/bin/python -B -m unittest tests.test_dispatcher_layer0 -v` → the three FAIL.

- [ ] **Step 3: Implement** — in `core/dispatcher/layer0.py`:
  - imports: `from core.search.page_extract import extract_first_url` and
    `page_read_enabled` alongside the existing `sense_enabled` import.
  - in `emit_spec`, next to the existing predicate locals (~:232):

```python
        owner_url_present = page_read_enabled() and bool(extract_first_url(utterance))
```

  - insert the arm ABOVE the `current_world_question` elif (after the
    `explicit_memory` arm), mirroring the current-world arm's body shape:

```python
        elif owner_url_present and not explicit_memory:
            substrate_sources = _available_substrates(
                inventory,
                _substrate_candidates(source_anchor_candidates),
            )
            external_sources = [ExternalSource.FETCH_URL]
            if substrate_sources:
                hint = CompositionHint.PARALLEL
                framing = ProvenanceFraming.HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES
            else:
                hint = CompositionHint.FRESH_ONLY
                framing = ProvenanceFraming.FRESH_ONLY
```

- [ ] **Step 4: GREEN** — full module: `.venv/bin/python -B -m unittest tests.test_dispatcher_layer0 -v` → PASS including all pre-existing arm tests (current-world, reddit, flag-off regression) untouched.
- [ ] **Step 5: Commit (behavior-affecting)**

```bash
git add core/dispatcher/layer0.py tests/test_dispatcher_layer0.py
git commit -m "feat(page-read): Layer0 arm — owner-named URLs select FETCH_URL

## Predicted effect
With MAEZ_PAGE_READ_ENABLED=1, a turn containing an explicit http(s) URL
composes FETCH_URL hybrid (URL wins precedence over current-world search
markers); flag unset or no URL: compositions byte-identical to today.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: The stomach — OR-gate + page observations (spec S2 + the Codex catch)

**Files:** Modify `core/intake_bus/world_observation_lane.py`, `core/brain/brain_loop.py` (stash block), `daemon/maez_daemon.py` (drain dispatch); test `tests/test_world_observation_lane.py`.

- [ ] **Step 1: Failing tests** — append to `tests/test_world_observation_lane.py` (reuse `_FakeMemory`; `_Turn` gains FETCH_URL variants):

```python
class PageObservationTests(unittest.TestCase):
    def setUp(self):
        for k in ("MAEZ_SEARCH_AS_SENSE_ENABLED", "MAEZ_PAGE_READ_ENABLED"):
            os.environ.pop(k, None)
            self.addCleanup(lambda k=k: os.environ.pop(k, None))

    def test_page_observation_writes_with_ONLY_page_flag(self):
        os.environ["MAEZ_PAGE_READ_ENABLED"] = "1"  # search flag ABSENT — the Codex catch
        mem = _FakeMemory()
        out = lane.write_page_observation(
            mem, url="https://github.com/x/releases", title="Releases",
            excerpt="b9601 released June 11", diagnostic_id="diag-p1",
        )
        self.assertEqual(out, "admitted")
        rec = mem.stored[0]
        self.assertIn("https://github.com/x/releases", rec["content"])
        self.assertIn("Releases", rec["content"])

    def test_page_observation_disabled_when_neither_flag(self):
        mem = _FakeMemory()
        out = lane.write_page_observation(
            mem, url="https://a", title="t", excerpt="x", diagnostic_id="d1",
        )
        self.assertEqual(out, "disabled")
        self.assertEqual(mem.stored, [])

    def test_web_search_write_still_works_with_only_search_flag(self):
        os.environ["MAEZ_SEARCH_AS_SENSE_ENABLED"] = "1"
        mem = _FakeMemory()
        out = lane.write_world_observation(
            mem, query="q", evidence_texts=_evidence(), diagnostic_id="d2",
        )
        self.assertEqual(out, "admitted")

    def test_page_source_ref_and_reclass_metadata(self):
        os.environ["MAEZ_PAGE_READ_ENABLED"] = "1"
        mem = _FakeMemory()
        lane.write_page_observation(
            mem, url="https://a.example/p", title="T", excerpt="x", diagnostic_id="diag-9",
        )
        rec = mem.stored[0]
        self.assertTrue(rec["source_ref"].startswith("page_read:diag-9:"))
        md = rec["metadata"]
        self.assertEqual(md["owner_supplied_url"], "true")
        self.assertEqual(md["preflight_allowed"], "true")
        self.assertEqual(md["text_content_type"], "true")

    def test_page_observation_idempotent(self):
        os.environ["MAEZ_PAGE_READ_ENABLED"] = "1"
        mem = _FakeMemory(existing="row-1")
        out = lane.write_page_observation(
            mem, url="https://a", title="t", excerpt="x", diagnostic_id="diag-9",
        )
        self.assertEqual(out, "already_admitted")

    def test_condition_source_aware(self):
        self.assertTrue(lane.evaluate_write_condition(_Turn(sources=("FETCH_URL",), summaries=("FETCH_URL",)), source_value="FETCH_URL"))
        self.assertFalse(lane.evaluate_write_condition(_Turn(), source_value="FETCH_URL"))  # WEB_SEARCH turn, FETCH_URL probe
        self.assertTrue(lane.evaluate_write_condition(_Turn()))  # default stays WEB_SEARCH — existing callers unchanged
```

(`_FakeMemory.store` must record `source_ref` and `metadata` kwargs — extend
the fake if it doesn't; do not change the real bus.)

- [ ] **Step 2: RED** — `.venv/bin/python -B -m unittest tests.test_world_observation_lane -v` → new tests FAIL.

- [ ] **Step 3: Implement the lane** — in `core/intake_bus/world_observation_lane.py`:
  - import: `from core.search.sense_flag import page_read_enabled, sense_enabled`
  - the gate in `write_world_observation` becomes (and the same line in the
    new function below):

```python
    if not (sense_enabled() or page_read_enabled()):
        return "disabled"
```

  - `evaluate_write_condition` gains the source parameter (default keeps
    every existing caller/test green):

```python
def evaluate_write_condition(rendered_turn, source_value: str = "WEB_SEARCH") -> bool:
```

    and `_has_web_search`/`_summaries_include_web` become
    `_has_source(values, source_value)` / `_summaries_include(summaries,
    source_value)` — same bodies with the literal `"WEB_SEARCH"` replaced by
    the parameter (keep thin `WEB_SEARCH`-named wrappers if other modules
    import the old names — check with one grep first).
  - add the page writer (mirrors `write_world_observation`'s admit flow):

```python
def write_page_observation(
    memory,
    *,
    url: str,
    title: str,
    excerpt: str,
    diagnostic_id: str,
) -> str:
    """Spec S2: the reclassification happens HERE, justified by three
    conditions that are true-by-construction for a successful FETCH_URL
    branch (the Layer0 arm only fires on an owner-named URL; a successful
    branch means preflights passed; the adapter guard means text content),
    and recorded as metadata so it is auditable, never silent."""
    if not (sense_enabled() or page_read_enabled()):
        return "disabled"
    try:
        url_hash = hashlib.sha256((url or "").encode("utf-8")).hexdigest()[:12]
        content_lines = [
            f"Page observation — page content entered the synthesis context for: {url[:200]}",
        ]
        if title:
            content_lines.append(f"title: {title[:200]}")
        if excerpt:
            content_lines.append(f"- {excerpt[:600]}")
        content_lines.append(f"observed_at: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
        fact = IntakeFact(
            source_kind="world_observation",
            source_ref=f"page_read:{diagnostic_id}:{url_hash}",
            content="\n".join(content_lines),
            provenance_source=ProvenanceSource.EXTERNAL_WEB,
            egress_origin_class=WORLD_OBSERVATION_EGRESS,
            promotion_posture=PromotionPosture.ADMIT_TO_BODY,
            fetch_batch_id=str(diagnostic_id),
            metadata={
                "lane": "world_observation",
                "kind": "page_read",
                "owner_supplied_url": "true",
                "preflight_allowed": "true",
                "text_content_type": "true",
            },
        )
        outcome = admit(_SingleFactAdapter(fact), memory)
        logger.info("world_observation lane: %s ref=%s", outcome.status, outcome.source_ref)
        return outcome.status if outcome.status != "nothing_pending" else "skipped"
    except Exception as e:
        logger.warning("page_observation dropped: %s", e)
        return "error_dropped"
```

- [ ] **Step 4: Extend the brain_loop stash block** (the 0c-recorded block, ~:878): after the existing WEB_SEARCH branch loop, add the FETCH_URL case so the stash carries a page observation payload — replace the block's `observation=(...)` construction with:

```python
              _page_texts = []
              for _branch in getattr(external_result, "branch_results", []) or []:
                  if str(getattr(getattr(_branch, "source", None), "value", "")) == "FETCH_URL":
                      _page_texts = [
                          getattr(_block, "text", "") or ""
                          for _block in (getattr(_branch, "blocks", ()) or ())
                      ][:1]
                      break
              _observation = None
              if evaluate_write_condition(rendered_turn):
                  _observation = {
                      "query": user_text,
                      "evidence_texts": _web_texts,
                      "diagnostic_id": str(getattr(external_result, "fanout_generation_id", "")),
                  }
              elif _page_texts and evaluate_write_condition(rendered_turn, source_value="FETCH_URL"):
                  from core.search.page_extract import extract_first_url

                  _first = _page_texts[0]
                  _title, _, _rest = _first.partition("\n")
                  _observation = {
                      "kind": "page_read",
                      "url": extract_first_url(user_text) or "",
                      "title": _title.strip()[:200],
                      "excerpt": (_rest or _first).strip()[:600],
                      "diagnostic_id": str(getattr(external_result, "fanout_generation_id", "")),
                  }
              stash_turn_evidence(
                  chat_id,
                  rendered_turn=rendered_turn,
                  evidence_texts=_web_texts or _page_texts,
                  observation=_observation,
              )
```

(Keep the surrounding `if sense_enabled():` guard but widen it to
`if sense_enabled() or page_read_enabled():` — same OR rule as the lane.)

- [ ] **Step 5: The daemon drain dispatches on kind** — at the 0c-recorded drain (~:6790), replace the write call:

```python
                if _turn_ev.get("observation"):
                    _obs = dict(_turn_ev["observation"])
                    if _obs.pop("kind", None) == "page_read":
                        from core.intake_bus.world_observation_lane import write_page_observation

                        write_page_observation(self.memory, **_obs)
                    else:
                        from core.intake_bus.world_observation_lane import write_world_observation

                        write_world_observation(self.memory, **_obs)
```

- [ ] **Step 6: GREEN (the full matrix)** —

```bash
.venv/bin/python -B -m unittest tests.test_world_observation_lane tests.test_attribution_render tests.test_dispatcher_layer0 -v 2>&1 | tail -4
```
Expected: PASS — including every pre-existing WEB_SEARCH lane test unmodified.

- [ ] **Step 7: Commit (behavior-affecting)**

```bash
git add core/intake_bus/world_observation_lane.py core/brain/brain_loop.py daemon/maez_daemon.py tests/test_world_observation_lane.py
git commit -m "feat(page-read): page observations through the shared stomach (OR-gate)

## Predicted effect
With MAEZ_PAGE_READ_ENABLED=1 (search-sense flag irrelevant — the shared
lane's write gate is now sense OR page_read), an evidence-admitted
FETCH_URL turn writes exactly ONE page_read:<diag>:<urlhash> observation
(external_web/untrusted, three audited reclassification booleans,
idempotent). WEB_SEARCH observations unchanged. Neither flag: zero writes,
byte-identical.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Source-specific progress (spec S3)

**Files:** Modify `core/brain/brain_loop.py` (`_emit_search_progress`, :81); test `tests/test_world_observation_lane.py` (`ProgressEmitTests` lives there).

- [ ] **Step 1: Failing test** — extend `ProgressEmitTests`:

```python
    def test_page_read_wording_is_source_specific(self):
        from core.brain.brain_loop import _emit_search_progress

        calls = []
        _emit_search_progress(calls.append, ["FETCH_URL"], stage="start", count=None)
        _emit_search_progress(calls.append, ["WEB_SEARCH"], stage="start", count=None)
        _emit_search_progress(calls.append, ["LIVE_REDDIT"], stage="start", count=None)
        self.assertEqual(calls, ["reading the page...", "searching the web..."])
```

- [ ] **Step 2: RED** → the FETCH_URL call currently emits nothing.

- [ ] **Step 3: Implement** — `_emit_search_progress` becomes source-aware (keep the existing signature; ASCII ellipsis matches the v0.1 convention):

```python
def _emit_search_progress(send_intermediate, external_sources, *, stage: str, count):
    """True-by-construction progress, source-specific wording (spec S3).
    Fires only when the source was actually selected and the fanout reached
    this stage. Never narrates thought. Silent no-op without a sender."""
    if send_intermediate is None:
        return
    names = {str(getattr(s, "value", s)) for s in (external_sources or [])}
    text = None
    if stage == "start":
        if "FETCH_URL" in names:
            text = "reading the page..."
        elif "WEB_SEARCH" in names:
            text = "searching the web..."
    elif stage == "results" and count is not None and "WEB_SEARCH" in names:
        text = f"reading {count} results..."
    if not text:
        return
    try:
        send_intermediate(text)
    except Exception:
        logging.getLogger("maez").debug("search progress emit failed", exc_info=True)
```

(FETCH_URL precedence in the wording mirrors the Layer0 precedence; the
existing wiring at :762 passes `spec.external_sources` already and needs no
change. The Task-4-of-search-sense pass-through gate stays on
`sense_enabled()` — extend it to `sense_enabled() or page_read_enabled()`
at the :1832 call site so page-read-only configs still get their notice;
include that one-line change in this commit.)

- [ ] **Step 4: GREEN** — `tests.test_world_observation_lane` + the existing progress tests → PASS.
- [ ] **Step 5: Commit (behavior-affecting)**

```bash
git add core/brain/brain_loop.py tests/test_world_observation_lane.py
git commit -m "feat(page-read): source-specific progress — 'reading the page...'

## Predicted effect
FETCH_URL turns show 'reading the page...' (never search wording); the
progress pass-through now also enables under MAEZ_PAGE_READ_ENABLED alone.
WEB_SEARCH wording and the one-notice sender policy unchanged.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 8: Verification floor + STOP-at-gate handoff

**Files:** Create `docs/handoffs/2026-06-12-page-read-gate.md`.

- [ ] **Step 1: Focused suite**

```bash
.venv/bin/python -B -m unittest \
  tests.test_page_extract tests.test_egress_external_fetch_substrate \
  tests.test_dispatcher_external_sources tests.test_dispatcher_layer0 \
  tests.test_world_observation_lane tests.test_attribution_render \
  tests.test_web_search_sense tests.test_searxng_client \
  tests.test_search_commitment tests.test_surface_adapter \
  -v 2>&1 | tail -5
```
Expected: ALL PASS.

- [ ] **Step 2: ruff**

```bash
.venv/bin/ruff check core/search/page_extract.py core/search/sense_flag.py \
  core/egress/external_fetch.py core/dispatcher/external_sources.py \
  core/dispatcher/layer0.py core/intake_bus/world_observation_lane.py \
  core/brain/brain_loop.py daemon/maez_daemon.py tests/test_page_extract.py
```
Expected: `All checks passed!`

- [ ] **Step 3: Write the handoff** — create `docs/handoffs/2026-06-12-page-read-gate.md`:

```markdown
# Page-Read Sense v0 — For Cross-Lane Review

## Status
Built, stopped at the gate. No merge, restart, flag, or service changes.
Branch: page-read-sense-v0.

## Task 0 proofs (paste actual outputs)
- 0a adapter/preflights: <lines>
- 0b content_type threading: <construction site + helper>
- 0c lane gate + stash + drain: <lines>

## Review anchors
1. Flag matrix on the shared stomach: neither/search-only/page-only/both —
   page observation writes with ONLY MAEZ_PAGE_READ_ENABLED=1 (the Codex
   catch); WEB_SEARCH path unchanged.
2. Raw HTML never reaches evidence (extraction inside the adapter; bounded).
3. content-type guard real (header-populated field, text-only acceptance).
4. Preflight rails untouched and green: MODEL_INVENTED_URL, sensitive-query,
   subject-boundary, scheme/private-IP/size in external_fetch.
5. Layer0: URL wins precedence over current-world markers; flag-off and
   no-URL byte-identical; current-world + reddit arms untouched.
6. Reclassification auditable: the three metadata booleans present on every
   page observation; source_ref page_read:<diag>:<urlhash>; idempotent.
7. Progress: "reading the page..." only on real FETCH_URL fanout start.

## Verification (paste outputs)
<suite + ruff>

## Owner witness after review + merge (spec's 6 steps)
1. MAEZ_PAGE_READ_ENABLED=1 in model.env (witness comment + revert line);
   restart maez.service.
2. Paste: "check https://github.com/ggml-org/llama.cpp/releases — what's
   the latest release?" → expect "reading the page..." → the version
   number, finally, in Maez's voice.
3. /receipts → the page URL as source.
4. Memory: one page_read observation w/ the three booleans; repeat → no
   duplicate.
5. "check that page we talked about" (no URL) → no page-read, honest reply.
6. A direct PDF link → honest "couldn't read that page."
```

- [ ] **Step 4: Commit + STOP**

```bash
git add docs/handoffs/2026-06-12-page-read-gate.md
git commit -m "docs(page-read): STOP-at-gate handoff

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

**STOP.** Report branch tip + verification. Claude reviews (covenant axis), then the owner takes the breaths.

---

## Self-Review

1. **Spec coverage:** S1 content-type→Tasks 2+4; digestion→Tasks 3+4; nerve+precedence→Task 5; S2 reclassification w/ booleans + OR-gate (Codex catch)→Task 6; S3 wording→Task 7; witness/no-URL rewording→Task 8 handoff; flag→Task 1; preflights-untouched→Tasks 4+8 anchors. ✓
2. **Placeholders:** Task 2 Step 1 contains one bounded fixture-adaptation instruction (copy the file's existing response-fake) with the assertion stated — the file is 32 lines, the fake shape is there; everything else is complete code. ✓
3. **Type consistency:** `page_read_enabled()` (Tasks 1,5,6,7); `extract_readable(raw, *, content_type) -> (title, text)` (Tasks 3,4); `extract_first_url` (Tasks 3,5,6); `write_page_observation(memory, *, url, title, excerpt, diagnostic_id)` (Task 6, drain in same task); `evaluate_write_condition(rendered_turn, source_value="WEB_SEARCH")` default keeps existing callers (Task 6). ✓
```
