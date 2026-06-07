# Chat Photo Vision v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Build the missing `tools/vision_tools.py:vision_analyze_tool`, pointed at the local `:8082`/`maez-vision` (LFM), behind a loopback gate + cache containment, and wire the Telegram photo path — so Maez can see photos you send, raw pixels never leaving the box.

**Architecture:** A new `tools/vision_tools.py` reuses `screen_perception`'s env-driven `VISION_URL`/`VISION_MODEL`, validates loopback + cache-containment before sending, downscales to 1024, POSTs the multimodal call, returns `{"success","analysis","error"}`. The Telegram photo-batch-flush seam calls it (≤3/album + overflow), folding the analysis into `event.text`. Stickers (already calling the tool) light up for free.

**Tech Stack:** Python 3, `unittest` (NOT pytest — `.venv/bin/python -B -m unittest`), `requests`/`PIL` (already used by `screen_perception`). Reuse: `screen_perception.VISION_URL/VISION_MODEL`, `platform_base.get_image_cache_dir`.

**Spec:** `docs/superpowers/specs/2026-06-06-chat-photo-vision-v0-design.md`. **Lane:** Codex implements / Claude reviews. Apples-to-apples full `discover` in `/home/rohit/maez`.

**Headline rails (test-enforced, review anchors):** raw image is **loopback-only** (refuse non-127.0.0.1 `VISION_URL`, send zero bytes) and **cache-contained** (`image_url` only under the image cache); **no cloud egress of raw image**; **no durable image archive**; no-fabrication fail-safe.

---

### Task 1: `tools/vision_tools.py` skeleton + JSON contract + importable package

**Files:**
- Create: `tools/vision_tools.py`, `tools/__init__.py` (if `tools` isn't already a package — the import `from tools.vision_tools import …` must resolve)
- Test: `tests/test_vision_tools.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_vision_tools.py
import json, unittest, asyncio
from tools import vision_tools

def run(coro): return asyncio.get_event_loop().run_until_complete(coro)

class ContractTests(unittest.TestCase):
    def test_result_shape(self):
        out = vision_tools._result(success=True, analysis="a cat on a desk")
        self.assertEqual(set(out), {"success", "analysis", "error"})
        self.assertTrue(out["success"]); self.assertEqual(out["analysis"], "a cat on a desk")
    def test_emit_is_json_string(self):
        s = vision_tools._emit(vision_tools._result(success=False, error="x"))
        d = json.loads(s); self.assertFalse(d["success"]); self.assertEqual(d["error"], "x")
```

- [ ] **Step 2: Run → FAIL** (`No module named 'tools.vision_tools'`).
Run: `.venv/bin/python -B -m unittest tests.test_vision_tools.ContractTests -v`

- [ ] **Step 3: Implement**

```python
# tools/vision_tools.py
"""Local vision tool: analyze an owner-provided cached image via the local
vision endpoint. Raw image bytes are LOOPBACK-ONLY and CACHE-CONTAINED."""
import json

def _result(success: bool, analysis: str = "", error: str = "") -> dict:
    return {"success": bool(success), "analysis": analysis, "error": error}

def _emit(result: dict) -> str:
    return json.dumps(result)
```
(Create empty `tools/__init__.py` if missing.)

- [ ] **Step 4: Run → PASS.** **Step 5: Commit** `feat(vision): vision_tools contract skeleton`.

---

### Task 2: Loopback hard gate (HEADLINE)

**Files:** Modify `tools/vision_tools.py`; Test `tests/test_vision_tools.py`

- [ ] **Step 1: Failing test**

```python
# append
from unittest import mock
class LoopbackGateTests(unittest.TestCase):
    def test_remote_url_refused_zero_bytes(self):
        with mock.patch.object(vision_tools, "VISION_URL", "http://10.0.0.5:8082/v1/chat/completions"), \
             mock.patch.object(vision_tools, "requests") as rq:
            out = json.loads(run(vision_tools.vision_analyze_tool("/tmp/x.png", "describe")))
        self.assertFalse(out["success"]); self.assertEqual(out["error"], "non_local_vision_endpoint")
        rq.post.assert_not_called()           # zero bytes left the box
    def test_loopback_allowed(self):
        for u in ("http://127.0.0.1:8082/v1/chat/completions","http://localhost:8082/v1/x","http://[::1]:8082/x"):
            self.assertTrue(vision_tools._is_loopback_url(u), u)
        self.assertFalse(vision_tools._is_loopback_url("http://example.com/x"))
```

- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement**

```python
# tools/vision_tools.py
import socket
from urllib.parse import urlparse
from skills.screen_perception import VISION_URL, VISION_MODEL  # reuse env-driven endpoint

_LOOPBACK = {"127.0.0.1", "::1", "localhost"}

def _is_loopback_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").strip().lower()
    if host in _LOOPBACK:
        return True
    try:  # resolve to be safe; all addrs must be loopback
        infos = socket.getaddrinfo(host, None)
        return bool(infos) and all(_addr_is_loopback(ai[4][0]) for ai in infos)
    except Exception:
        return False

def _addr_is_loopback(addr: str) -> bool:
    import ipaddress
    try: return ipaddress.ip_address(addr.split("%")[0]).is_loopback
    except Exception: return False

async def vision_analyze_tool(image_url: str, user_prompt: str) -> str:
    if not _is_loopback_url(VISION_URL):
        return _emit(_result(False, error="non_local_vision_endpoint"))
    # cache containment + call follow (Tasks 3-4)
    return _emit(_result(False, error="not_implemented"))
```

- [ ] **Step 4: Run → PASS.** **Step 5: Commit** `feat(vision): loopback hard gate — raw image never leaves localhost`.

---

### Task 3: Cache containment (HEADLINE)

**Files:** Modify `tools/vision_tools.py`; Test `tests/test_vision_tools.py`

- [ ] **Step 1: Failing test**

```python
# append
import os, tempfile
class CacheContainmentTests(unittest.TestCase):
    def _cache(self): from skills.surface.platform_base import get_image_cache_dir; return get_image_cache_dir()
    def test_in_cache_ok(self):
        p = os.path.join(self._cache(), "vt_test.png"); open(p,"wb").write(b"\x89PNG")
        self.assertTrue(vision_tools._valid_cache_image(p)); os.unlink(p)
    def test_rejects_outside_cache_and_schemes(self):
        for bad in ("/etc/passwd","http://x/y.png","../../etc/passwd","/tmp/elsewhere.png","nonexistent.png"):
            self.assertFalse(vision_tools._valid_cache_image(bad), bad)
    def test_rejects_symlink_escape(self):
        link = os.path.join(self._cache(),"vt_escape.png")
        try:
            if os.path.exists(link): os.unlink(link)
            os.symlink("/etc/passwd", link)
            self.assertFalse(vision_tools._valid_cache_image(link))
        finally:
            if os.path.islink(link): os.unlink(link)
```

- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement**

```python
# tools/vision_tools.py
import os
def _valid_cache_image(path: str) -> bool:
    if not path or "://" in path:
        return False
    try:
        from skills.surface.platform_base import get_image_cache_dir
        cache = os.path.realpath(get_image_cache_dir())
        real = os.path.realpath(path)
        if os.path.commonpath([cache, real]) != cache:
            return False
        return os.path.isfile(real) and not os.path.islink(path)
    except Exception:
        return False
```
Wire into `vision_analyze_tool` after the loopback gate: `if not _valid_cache_image(image_url): return _emit(_result(False, error="image_not_in_cache"))`.

- [ ] **Step 4: Run → PASS.** **Step 5: Commit** `feat(vision): cache-containment gate — image_url only under the image cache`.

---

### Task 4: Downscale (1024) + vision call + contract/fail-safe

**Files:** Modify `tools/vision_tools.py`; Test `tests/test_vision_tools.py`

- [ ] **Step 1: Failing test**

```python
# append
class CallTests(unittest.TestCase):
    def _img(self):
        from skills.surface.platform_base import get_image_cache_dir
        from PIL import Image; import os
        p = os.path.join(get_image_cache_dir(), "vt_big.png")
        Image.new("RGB",(2000,1500),(10,20,30)).save(p); return p
    def test_success_path_downscales_and_returns_analysis(self):
        sent = {}
        class Resp:
            status_code=200
            def json(self): return {"choices":[{"message":{"content":"a dark rectangle"}}]}
        def fake_post(url, json=None, timeout=None):
            sent["url"]=url
            b64 = json["messages"][0]["content"][1]["image_url"]["url"]
            sent["b64len"]=len(b64); return Resp()
        p=self._img()
        with mock.patch.object(vision_tools,"requests") as rq:
            rq.post.side_effect=fake_post
            out=json.loads(run(vision_tools.vision_analyze_tool(p,"describe")))
        self.assertTrue(out["success"]); self.assertEqual(out["analysis"],"a dark rectangle")
        self.assertIn("127.0.0.1", sent["url"])      # loopback
        import os; os.unlink(p)
    def test_vision_down_is_honest(self):
        p=self._img()
        with mock.patch.object(vision_tools,"requests") as rq:
            rq.post.side_effect=Exception("conn refused")
            out=json.loads(run(vision_tools.vision_analyze_tool(p,"describe")))
        self.assertFalse(out["success"]); self.assertEqual(out["analysis"],"")  # no fabrication
        import os; os.unlink(p)
```

- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** the body (after the two gates): load via PIL, `img.thumbnail((MAX,MAX))` with `MAX = int(os.environ.get("MAEZ_CHAT_PHOTO_VISION_MAX_DIM","1024"))`, base64-encode, `requests.post(VISION_URL, json={"model":VISION_MODEL,"max_tokens":400,"messages":[{"role":"user","content":[{"type":"text","text":user_prompt},{"type":"image_url","image_url":{"url":f"data:image/png;base64,{b64}"}}]}]}, timeout=60)`; on 200 parse `choices[0].message.content` → `_result(True, analysis=text)`; any exception/non-200/parse → `_result(False, error=<stage>)` (no analysis). Add `import requests`.

- [ ] **Step 4: Run → PASS.** **Step 5: Commit** with `## Predicted effect` (analyze a cached image via local LFM at 1024, honest on failure).

---

### Task 5: Telegram photo seam + album bound

**Files:** Modify `skills/surface/telegram_adapter.py` (the photo-batch-flush path); Test `tests/test_chat_photo_wiring.py`

**Context:** photos set `event.media_urls` and are batched (`_enqueue_photo_event`/`_queue_media_group_event` → flush at "Flushing photo batch", ~line 2863). Add the analysis at the flush seam, **before** `handle_message`.

- [ ] **Step 1: Failing test** — drive the flush with 4 cached images; assert `vision_analyze_tool` called exactly 3×, the 4th noted as overflow, analyses folded into `event.text`, and `handle_message` called after.

```python
# tests/test_chat_photo_wiring.py — sketch: mock vision_analyze_tool to return ok JSON,
# build an event with 4 media_urls under the cache, invoke the flush, assert:
#   - vision_analyze_tool call count == 3 (MAEZ_CHAT_PHOTO_MAX_IMAGES)
#   - "more image" overflow note present in event.text
#   - analyses appear in event.text
#   - handle_message awaited once, after analysis
```

- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** — in the flush path, for `event.media_urls[:MAEZ_CHAT_PHOTO_MAX_IMAGES]` call `await vision_analyze_tool(path, PHOTO_VISION_PROMPT)`, collect `analysis` on success (honest skip on failure), append `f"(+{n} more images not analyzed)"` if over cap, prepend/fold into `event.text`, then proceed to `handle_message`. Add a `PHOTO_VISION_PROMPT` constant. `MAX = int(os.environ.get("MAEZ_CHAT_PHOTO_MAX_IMAGES","3"))`.

- [ ] **Step 4: Run → PASS.** **Step 5: Commit** `feat(body-ui): wire Telegram photo path to vision_analyze_tool (album-bounded)`.

---

### Task 6: Headline rail tests — no-cloud-egress + no-persistence

**Files:** Test `tests/test_vision_tools.py`

- [ ] **Step 1:** Assert (a) across a success call, the **only** host any image-bearing POST hits is `127.0.0.1`/loopback (capture every `requests.post`); (b) after a call, **no image bytes written to durable memory** — only the pre-existing cache file exists; the tool itself writes no new persistent file. (No `memory/`/db write of image bytes.)
- [ ] **Step 2: Run → PASS.** **Step 3: Commit** `test(vision): enforce no-cloud-egress + no-durable-image-persistence`.

---

### Task 7: Regression + sticker fix confirmation

- [ ] **Step 1:** `.venv/bin/python -B -m unittest tests.test_vision_tools tests.test_chat_photo_wiring -v` → green.
- [ ] **Step 2:** Confirm the sticker path import now resolves (`from tools.vision_tools import vision_analyze_tool`) — stickers describe again (the free fix).
- [ ] **Step 3:** Full `discover` in `/home/rohit/maez`; floor matches the known ambient class; touched suites green.

---

### Task 8: Witness + finish

- [ ] **Step 1 (owner-run):** Precondition — `curl -s http://127.0.0.1:8082/v1/models` confirms `maez-vision` is the **LFM2.5-VL-1.6B** build (not the 450M bench leftover). Then send photos via Telegram (general scene / text-OCR / person-present / vision-down) and judge LFM: **good / weak / wrong**.
- [ ] **Step 2:** Update `project_cognition_live_state.md` with the outcome + LFM general-vision verdict.
- [ ] **Step 3:** Use **superpowers:finishing-a-development-branch** — local merge owner-delegable; no push. Desktop screen-OCR + the PipeWire capture fix remain the separate parallel track.
