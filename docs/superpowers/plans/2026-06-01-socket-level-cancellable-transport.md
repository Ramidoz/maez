# Socket-Level Cancellable Transport — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the llama.cpp streaming transport with one that owns the raw TCP socket from the moment the request is sent, so `cancel()` closes the socket *during* prompt-eval and frees the slot (~1.2s, probe-proven). Everything above the transport (gateway, priorities, `BrainPreempted`, telemetry, no-bypass) is unchanged.

**Architecture:** A standalone, socket-free **stateful incremental parser** (`_LlamaCppStreamParser`) handles HTTP/1.1 status + chunked transfer-encoding + SSE framing across arbitrary TCP fragmentation, with strict error rules. A thin **`_LlamaCppSocketStream`** owns the socket, feeds `recv()` bytes to the parser, and exposes an idempotent `close()`. `_start_llamacpp_stream` returns the socket stream; `CancellableBrainCall` wraps it as today.

**Tech Stack:** Python 3.14, `unittest` (NO pytest), `socket`, `urllib.parse`, existing `core/routing/llm_client.py` + `core/routing/cancellable_brain_call.py` + `core/routing/brain_gateway.py`.

**Spec:** `docs/superpowers/specs/2026-06-01-socket-level-cancellable-transport-design.md`

**Lane:** Codex implements, Claude cross-verifies, Rohit owner-runs the live gate. **Recall stays OFF.**

---

## File Structure

- `core/routing/llm_client.py` — add `_LlamaCppStreamParser` (parser) + `_LlamaCppSocketStream` (socket owner); rewrite `_start_llamacpp_stream` to return the socket stream; remove F2's `_LlamaCppRawSSEStream` (requests-based).
- `tests/test_llamacpp_stream_parser.py` — NEW: parser unit + fragmentation torture + strictness.
- `tests/test_llamacpp_socket_stream.py` — NEW: socket owner with a fake socket (send/recv/shutdown/close), cancel→clean-stop, https-reject, url-build.
- `tests/test_transport_early_handle.py` — REPLACE F2's requests mocks with fake-socket equivalents (handle-before-iteration, cancel frees promptly).
- `tests/test_brain_gateway_equivalence.py` — keep; ensure byte-equivalence holds via the socket parser.

---

## Task 0: Branch + reuse F2's diagnostic

- [ ] **Step 1:** From `main`, create branch `socket-cancellable-transport`.
- [ ] **Step 2:** Cherry-pick F2's gateway diagnostic commit (preempt-probe + witnessed schema evolution): `git cherry-pick 32e9c01`. Resolve trivially if needed. Do NOT cherry-pick the transport commits (`3bfd6e0`, `44d4e56`, `69cd6da`).
- [ ] **Step 3:** Run the gateway suite to confirm the cherry-pick is green: `.venv/bin/python -m unittest tests.test_brain_gateway tests.test_brain_gateway_preempt_probe tests.test_brain_gateway_forced_collision -v` → PASS.

---

## Task 1: `_LlamaCppStreamParser` — stateful incremental parser (socket-free)

**Files:** Modify `core/routing/llm_client.py`; Test `tests/test_llamacpp_stream_parser.py`.

- [ ] **Step 1: Write fragmentation + strictness tests FIRST**

```python
# tests/test_llamacpp_stream_parser.py
import unittest
from core.routing.llm_client import _LlamaCppStreamParser, BackendError

# A full, valid wire capture (status + chunked + SSE + DONE), as bytes.
WIRE = (
    b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n"
    b"Transfer-Encoding: chunked\r\n\r\n"
    b"3f\r\n"
    b'data: {"choices":[{"delta":{"role":"assistant","content":null}}]}\n\n'
    b"\r\n"
    b"2d\r\n"
    b'data: {"choices":[{"delta":{"content":"On April "}}]}\n\n'
    b"\r\n"
    b"27\r\n"
    b'data: {"choices":[{"delta":{"content":"27 [E1]"}}]}\n\n'
    b"\r\n"
    b"e\r\ndata: [DONE]\n\n\r\n"
    b"0\r\n\r\n"
)
# NOTE: chunk sizes above are illustrative; the Codex implementation MUST
# recompute real hex sizes for the test fixture (size = len of the chunk body
# bytes up to and including the trailing data block, excluding the chunk CRLF).
# Use a helper to build WIRE so sizes are always correct (see Step 1b).


def _feed_in_slices(parser, data: bytes, n: int):
    """Feed `data` to parser in n-byte slices; return concatenated tokens."""
    out = []
    for i in range(0, len(data), n):
        out.extend(parser.feed(data[i:i + n]))
    return "".join(out)


class ParserTest(unittest.TestCase):
    def test_parses_whole_buffer(self):
        p = _LlamaCppStreamParser()
        self.assertEqual(_feed_in_slices(p, WIRE, len(WIRE)), "On April 27 [E1]")
        self.assertTrue(p.done)

    def test_fragmentation_1_byte_at_a_time(self):
        p = _LlamaCppStreamParser()
        self.assertEqual(_feed_in_slices(p, WIRE, 1), "On April 27 [E1]")

    def test_fragmentation_adversarial_slices(self):
        for n in (2, 3, 5, 7, 13, 17, 64, 100):
            p = _LlamaCppStreamParser()
            self.assertEqual(_feed_in_slices(p, WIRE, n), "On April 27 [E1]", f"n={n}")

    def test_non_200_raises(self):
        p = _LlamaCppStreamParser()
        with self.assertRaises(BackendError):
            p.feed(b"HTTP/1.1 500 Internal Server Error\r\n\r\n")

    def test_malformed_json_without_cancel_raises(self):
        p = _LlamaCppStreamParser()
        head = b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n"
        p.feed(head)
        with self.assertRaises(BackendError):
            p.feed(b"12\r\ndata: {not json}\n\n\r\n")

    def test_empty_stream_without_cancel_raises_on_done(self):
        p = _LlamaCppStreamParser()
        head = b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n"
        p.feed(head)
        with self.assertRaises(BackendError):
            # DONE with zero content yielded -> empty normal stream is a failure
            p.feed(b"e\r\ndata: [DONE]\n\n\r\n0\r\n\r\n")

    def test_truncation_when_cancelled_is_silent(self):
        p = _LlamaCppStreamParser()
        p.cancelled = True   # our own close() requested
        head = b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n"
        # malformed/truncated AFTER cancel -> no raise; parser just yields nothing more
        self.assertEqual("".join(p.feed(head + b"12\r\ndata: {trunc")), "")
```

- [ ] **Step 1b: Add a correct-size WIRE builder** in the test so chunk hex sizes are never hand-miscounted:

```python
def _chunk(body: bytes) -> bytes:
    return f"{len(body):x}\r\n".encode() + body + b"\r\n"

def _build_wire(*sse_events: bytes) -> bytes:
    head = (b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n"
            b"Transfer-Encoding: chunked\r\n\r\n")
    body = b"".join(_chunk(e) for e in sse_events) + b"0\r\n\r\n"
    return head + body
# Replace the literal WIRE with _build_wire(event1, event2, ...).
```

- [ ] **Step 2: Run tests → fail** (`_LlamaCppStreamParser` undefined).

Run: `.venv/bin/python -m unittest tests.test_llamacpp_stream_parser -v` → FAIL.

- [ ] **Step 3: Implement the parser**

```python
class _LlamaCppStreamParser:
    """Incremental HTTP/1.1 + chunked + SSE parser. Stateful across feed()s so
    arbitrary TCP fragmentation is safe. Strict on real corruption; silent only
    when `cancelled` (our own close() was requested)."""

    def __init__(self):
        self._buf = bytearray()
        self._phase = "status"   # status -> headers -> size -> body -> trailer -> done
        self._chunk_left = 0
        self._sse = bytearray()
        self._yielded = False
        self.cancelled = False

    @property
    def done(self) -> bool:
        return self._phase == "done"

    def feed(self, data: bytes) -> list:
        if data:
            self._buf += data
        tokens = []
        advanced = True
        while advanced and self._phase != "done":
            advanced = False
            if self._phase == "status":
                i = self._buf.find(b"\r\n")
                if i >= 0:
                    parts = bytes(self._buf[:i]).split(b" ", 2)
                    del self._buf[:i + 2]
                    code = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
                    if code != 200 and not self.cancelled:
                        raise BackendError(f"llamacpp non-200: {code}")
                    self._phase = "headers"; advanced = True
            elif self._phase == "headers":
                i = self._buf.find(b"\r\n")
                if i == 0:
                    del self._buf[:2]; self._phase = "size"; advanced = True
                elif i > 0:
                    del self._buf[:i + 2]; advanced = True   # drop one header line
            elif self._phase == "size":
                i = self._buf.find(b"\r\n")
                if i >= 0:
                    sizeline = bytes(self._buf[:i]).split(b";", 1)[0].strip()
                    del self._buf[:i + 2]
                    try:
                        n = int(sizeline, 16)
                    except ValueError:
                        if self.cancelled:
                            self._phase = "done"; break
                        raise BackendError("llamacpp bad chunk size")
                    if n == 0:
                        self._phase = "done"
                    else:
                        self._chunk_left = n; self._phase = "body"
                    advanced = True
            elif self._phase == "body":
                if self._chunk_left and self._buf:
                    take = min(self._chunk_left, len(self._buf))
                    self._sse += self._buf[:take]; del self._buf[:take]
                    self._chunk_left -= take; advanced = True
                if self._chunk_left == 0:
                    self._phase = "trailer"; advanced = True
            elif self._phase == "trailer":
                if len(self._buf) >= 2:
                    del self._buf[:2]; self._phase = "size"; advanced = True
            tokens.extend(self._drain_sse())
        if self._phase == "done" and not self._yielded and not self.cancelled:
            raise BackendError("llamacpp empty stream")
        return tokens

    def _drain_sse(self) -> list:
        out = []
        while True:
            i = self._sse.find(b"\n\n")
            if i < 0:
                break
            event = bytes(self._sse[:i]); del self._sse[:i + 2]
            for line in event.split(b"\n"):
                if not line.startswith(b"data:"):
                    continue
                payload = line[5:].strip()
                if payload == b"[DONE]":
                    self._phase = "done"; continue
                try:
                    obj = json.loads(payload)
                    choices = obj.get("choices") or [{}]
                    first = choices[0] or {}
                    delta = first.get("delta") or {}
                    message = first.get("message") or {}
                    content = delta.get("content") or message.get("content") or ""
                except Exception:
                    if self.cancelled:
                        return out
                    raise BackendError("llamacpp malformed SSE json")
                content = _strip_special_tokens(content or "")
                if content:
                    self._yielded = True
                    out.append(content)
        return out
```

- [ ] **Step 4: Run tests → pass.** Iterate on the parser until all fragmentation + strictness tests are green.

- [ ] **Step 5: Commit** `feat(transport): stateful incremental llama.cpp SSE parser`.

---

## Task 2: `_LlamaCppSocketStream` — socket owner

**Files:** Modify `core/routing/llm_client.py`; Test `tests/test_llamacpp_socket_stream.py`.

- [ ] **Step 1: Write tests with a fake socket**

```python
# tests/test_llamacpp_socket_stream.py
import threading, time, unittest
from core.routing.llm_client import _LlamaCppSocketStream, BackendError


class _FakeSocket:
    def __init__(self, script: list[bytes], block_event=None):
        self._script = list(script)
        self._block = block_event
        self.shutdown_calls = 0
        self.closed = False
        self.sent = bytearray()
    def sendall(self, data): self.sent += data
    def recv(self, n):
        if self.closed:
            raise OSError("socket closed")
        if self._script:
            return self._script.pop(0)
        if self._block is not None:
            self._block.wait(timeout=2.0)   # block like a server mid-eval
            raise OSError("closed during block")
        return b""
    def shutdown(self, how): self.shutdown_calls += 1
    def close(self): self.closed = True; (self._block.set() if self._block else None)


class SocketStreamTest(unittest.TestCase):
    def test_iterates_tokens(self):
        wire = [  # arbitrary fragmentation
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n",
            b"1f\r\ndata: {\"choices\":[{\"delta\":{\"content\":\"OK\"}}]}\n\n\r\n",
            b"e\r\ndata: [DONE]\n\n\r\n0\r\n\r\n",
        ]
        s = _LlamaCppSocketStream(sock=_FakeSocket(wire))
        self.assertEqual("".join(r.message.content for r in s), "OK")

    def test_close_is_idempotent_and_shuts_down(self):
        fs = _FakeSocket([])
        s = _LlamaCppSocketStream(sock=fs)
        s.close(); s.close()
        self.assertTrue(fs.closed)
        self.assertEqual(fs.shutdown_calls, 1)  # shutdown called once, guarded

    def test_close_unblocks_iteration_cleanly(self):
        block = threading.Event()
        fs = _FakeSocket([b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n"],
                         block_event=block)
        s = _LlamaCppSocketStream(sock=fs)
        out = []
        def run():
            for r in s:
                out.append(r.message.content)
        t = threading.Thread(target=run); t.start()
        time.sleep(0.1)
        s.close()                 # cross-thread cancel
        t.join(timeout=2.0)
        self.assertFalse(t.is_alive())   # iteration stopped cleanly (no raise)
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement the socket stream**

```python
import socket as _socket
import threading
from urllib.parse import urlparse


class _LlamaCppSocketStream:
    """Owns a raw socket; close() frees the server slot mid-eval."""

    def __init__(self, *, sock):
        self._sock = sock
        self._parser = _LlamaCppStreamParser()
        self._closed = False
        self._lock = threading.Lock()

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._parser.cancelled = True
            try:
                self._sock.shutdown(_socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self._sock.close()
            except OSError:
                pass

    def __iter__(self):
        while True:
            try:
                data = self._sock.recv(65536)
            except OSError:
                if self._closed:
                    return            # our own cancel -> clean stop -> BrainPreempted
                raise
            if not data:
                # connection ended; flush any final tokens, then stop
                for tok in self._parser.feed(b""):
                    yield _LlmResponse(message=_LlmMessage(content=tok, thinking=None))
                return
            for tok in self._parser.feed(data):
                yield _LlmResponse(message=_LlmMessage(content=tok, thinking=None))
            if self._parser.done:
                return
```

- [ ] **Step 4: Run → pass.**
- [ ] **Step 5: Commit** `feat(transport): socket owner with idempotent shutdown+close`.

---

## Task 3: `_start_llamacpp_stream` builds the connection (url via urllib.parse, reject https)

**Files:** Modify `core/routing/llm_client.py`; Test extends `tests/test_llamacpp_socket_stream.py`.

- [ ] **Step 1: Test url-build + https reject**

```python
    def test_https_base_url_rejected(self):
        with self.assertRaises(BackendError):
            llm_client._connect_llamacpp_socket("https://127.0.0.1:8443/v1", b"{}")

    def test_endpoint_path_from_base_url(self):
        # monkeypatch socket.create_connection to capture host/port + sent bytes
        ...
        self.assertIn(b"POST /v1/chat/completions HTTP/1.1", captured_sent)
```

- [ ] **Step 2: Implement connect + send + rewrite `_start_llamacpp_stream`**

```python
def _connect_llamacpp_socket(base_url: str, body: bytes):
    parsed = urlparse(base_url)
    if parsed.scheme != "http":
        raise BackendError(f"socket transport requires http, got {parsed.scheme!r}")
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 80
    path = (parsed.path.rstrip("/") or "") + "/chat/completions"
    sock = _socket.create_connection((host, port), timeout=90)
    head = (
        f"POST {path} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        f"Authorization: Bearer llamacpp\r\n"
        f"Content-Type: application/json\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"Connection: close\r\n\r\n"
    ).encode("utf-8")
    sock.sendall(head + body)
    return sock


def _start_llamacpp_stream(*, model, messages, temperature, max_tokens,
                           extra_body, timeout_s=None):
    payload = {
        "model": model, "messages": messages, "temperature": temperature,
        "max_tokens": max_tokens, "stream": True,
    }
    if extra_body:
        payload.update(extra_body)
    body = json.dumps(payload).encode("utf-8")
    sock = _connect_llamacpp_socket(LLAMACPP_BASE_URL, body)
    return _LlamaCppSocketStream(sock=sock)
```

Remove F2's `_LlamaCppRawSSEStream` and its `requests`-based `_start_llamacpp_stream`. Keep `requests` import only if still used elsewhere (check `_chat_ollama`); otherwise drop it.

- [ ] **Step 3: Run → pass.**
- [ ] **Step 4: Commit** `feat(transport): wire socket stream into _start_llamacpp_stream`.

---

## Task 4: Replace F2 transport tests + byte-equivalence

**Files:** `tests/test_transport_early_handle.py`, `tests/test_brain_gateway_equivalence.py`.

- [ ] **Step 1:** Rewrite `test_transport_early_handle.py` to mock `socket.create_connection` (returning a `_FakeSocket` whose `recv` blocks until `close()`), asserting `start_cancellable_chat` returns a handle **before** any body byte and that `cancel()` stops it < 800ms. (The handle exists right after `sendall`, before `recv`.)
- [ ] **Step 2:** Ensure `test_brain_gateway_equivalence.py` still passes: a non-preempted background buffered reply assembled via the socket parser equals the prior path for the same event sequence (feed a `_FakeSocket` with a known wire script; `collect()` equals expected).
- [ ] **Step 3: Run both → pass.**
- [ ] **Step 4: Commit** `test(transport): socket-based early-handle + equivalence`.

---

## Task 5: Cross-thread cancel → BrainPreempted (integration through the gateway)

**Files:** `tests/test_brain_gateway_forced_collision.py` (extend or reuse the fixed-contract test).

- [ ] **Step 1:** Add a collision test where the background `run_streaming_fn` returns a `CancellableBrainCall` wrapping a `_LlamaCppSocketStream` over a `_FakeSocket` that blocks in `recv` (models prompt-eval). Foreground `owner_recall` preempts; assert: foreground reply correct, foreground_ms < 1500, background raised `BrainPreempted`, no `preempt_timeout`.
- [ ] **Step 2: Run → pass.**
- [ ] **Step 3: Commit** `test(transport): gateway preempts socket-backed background -> BrainPreempted`.

---

## Task 6: Regression sweep + acceptance note

- [ ] **Step 1: No-bypass invariant** still green.
- [ ] **Step 2: Full gateway + transport + parser suite**

Run: `.venv/bin/python -m unittest tests.test_brain_gateway tests.test_brain_gateway_routing tests.test_brain_gateway_forced_collision tests.test_brain_gateway_equivalence tests.test_brain_preempt_propagation tests.test_cancellable_brain_call tests.test_brain_gateway_preempt_probe tests.test_llamacpp_stream_parser tests.test_llamacpp_socket_stream tests.test_transport_early_handle -v` → ALL PASS.

- [ ] **Step 3: Transport-adjacent floor** — run the brain-call-path modules (test_brain_loop, test_llm_client_generate_timeout, test_grounding_judge_circuit, test_evolution_engine_timeout, test_entity_llm_extractor, test_smoke_imports, test_observability, test_runtime_self_truth, test_next_step_proposer). Expected: no NEW failures vs base.
- [ ] **Step 4: Floor both directions** on a clean checkout (NOT git stash); name the known-unrelated flaky trio (egress / web-slice / import-shim) explicitly.
- [ ] **Step 5: Acceptance-gate note (owner-run, separate)** — reuse `docs/slices/brain-gateway/preempt-effectiveness-acceptance.md` (cherry-picked) with the adjusted bar: **abort releases ≤ ~1.5s**, background `preempted=true`, no `preempt_timeout`, no retry, no partial store, six-prompt p95 under A7, voice + inner-life intact. **Owner-run; recall stays OFF.**
- [ ] **Step 6: Commit** `test(transport): regression sweep + acceptance note`.

---

## Self-Review

- **Spec coverage:** §2 parser+socket+wiring → Tasks 1-3; strictness rules → Task 1 tests; fragmentation mandatory → Task 1 (1-byte + adversarial slices); url/https → Task 3; §3 unchanged-structure → only `_start_llamacpp_stream` body changes + Task 0 cherry-pick; §5 gate → Task 6 Step 5; §6 hermetic-first/unittest/floor → Tasks 1-2 socket-free/fake-socket, Task 6.
- **No placeholders:** parser + socket + connect code are concrete; the one literal to compute is the test WIRE chunk sizes — handled by the `_build_wire`/`_chunk` helper so Codex never hand-counts hex.
- **Covenant line:** strict on real corruption (non-200, malformed, empty) → `BackendError`; silent only when `cancelled`/`_closed` → clean stop → `BrainPreempted`. Tested both sides.
- **Risk flag for Codex:** the parser is the only intricate unit — treat the fragmentation tests as the contract; if the reference `feed()` mishandles a boundary, fix the parser, not the tests. The `recv()`-1-byte torture case is the strongest guard.
