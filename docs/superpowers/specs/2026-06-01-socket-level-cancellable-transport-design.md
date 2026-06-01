# Socket-Level Cancellable Transport for llama.cpp — Design

**Date:** 2026-06-01
**Status:** Draft under review (owner review pending before plan/Codex)
**Supersedes the transport of:** `docs/superpowers/specs/2026-06-01-brain-gateway-preempt-effectiveness-design.md` (F2 raw-`requests` approach — kept the diagnostic, replaced the transport)
**Lane:** Codex implements, Claude cross-verifies, Rohit owner-runs the live gate. **Recall stays OFF.**

---

## 1. Why (proven, not hypothesized)

The Brain Gateway preempts an in-flight background brain call by closing its stream so a foreground recall can own the single llama-server slot. The slice-blocking failure was that the cancel handle did not exist during **prompt-eval**, so a cold collision still waited 10-15s.

Two owner-run probes settled the layer:
- **`tools/probes/llamacpp_stream_handle_microprobe.py`** (production path, F2): cold `production_handle_returned_ms=9650` — `requests.post(stream=True)` does not expose the socket until **after** headers (post-eval). So F2 cannot close mid-eval. **F2 branch stays UNMERGED.**
- **`tools/probes/socket_mideval_abort_probe.py`** (committed `7e04e75`): controlled — **CLOSE mid-eval → follow-up TTFB ~1.2s (4/4: 1147/1204/1255/1394ms); NOCLOSE → ~7s** (eval remainder); daemon-cycle collisions ~17-24s separable by magnitude. The only difference between 1.2s and 7s is the socket close ⇒ **llama-server detects client disconnect during prompt-eval and abandons the slot in ~1.2s.**

**Conclusion: one-slot mid-eval preemption is physically achievable — at the socket layer. No second slot, no MTP, no cycle rescheduling. The fix is a transport that owns the raw socket fd from the moment the request is sent, so `cancel()` can close it during eval.**

## 2. The fix

Replace the llama.cpp streaming stream-start so it issues the request over a **raw TCP socket** and exposes that socket as the cancellation handle. Everything else in the Brain Gateway stack is unchanged.

### Component: `_LlamaCppSocketStream` (new, in `core/routing/llm_client.py`)

Owns one `socket.socket`. Responsibilities:
- **Construct/send:** build the endpoint from `LLAMACPP_BASE_URL` with `urllib.parse` (NOT hardcoded host/path) — parse scheme/host/port/path, endpoint path = `urlparse.path + "/chat/completions"`, default port 80. **Reject `https` explicitly** (`BackendError` — this raw-socket slice does no TLS). Then `socket.create_connection((host, port))`; send a manual HTTP/1.1 POST (headers + JSON body) with `Connection: close`. The socket (and thus `close()`) exists immediately after `sendall`, **before** the server responds — this is the property the probe proved.
- **`close()`** (idempotent, lock-protected): `socket.shutdown(SHUT_RDWR)` then `socket.close()`, guarded by a `_closed` flag + `threading.Lock`. **Catch and ignore `OSError` from `shutdown()`** (the socket may be half-closed or never fully connected); always proceed to `close()`. `shutdown` first makes cancellation forceful + deterministic (immediate FIN/RST) rather than waiting on GC/refcount. This is what frees the server slot (~1.2s server-side).
- **`__iter__`:** lazily read + parse the response off the socket and yield ollama-shaped `_LlmResponse(message=_LlmMessage(content=token, thinking=None))` tokens. Parsing (concrete, from a live capture):
  1. Read until `\r\n\r\n`; verify status line is `HTTP/1.1 200`.
  2. De-chunk the body: read a hex size line `<hex>\r\n`, read that many bytes, consume the trailing `\r\n`; stop at size `0`.
  3. Within the de-chunked stream, split SSE events on `\n\n`; for each `data: ` line, `[DONE]` ends the stream, else `json.loads` and take `choices[0].delta.content` (fall back to `choices[0].message.content`); skip `null`/empty; strip special tokens.

  **Strictness rule (covenant-safe — strict for real corruption, gentle only for our own deliberate cancel).** The stream's own `_closed` flag (set by `close()`, which `CancellableBrainCall.cancel()` calls) IS the "cancellation requested" signal:
  - **non-200** (before cancellation) → `BackendError` (after closing).
  - **malformed chunk/SSE framing** while `not _closed` → `BackendError`.
  - **socket error / truncation while `_closed`** → stop iteration cleanly (return), so `CancellableBrainCall` converts the cancelled-generator end into `BrainPreempted`.
  - **clean completion (`[DONE]`/socket end) that yielded ZERO content** while `not _closed` → `BackendError` (empty normal stream is a failure, never silent success). Track a "yielded any content" flag to detect this.

### Wiring: `_start_llamacpp_stream` returns `_LlamaCppSocketStream`

`start_cancellable_chat` keeps wrapping it in `CancellableBrainCall(raw_stream=stream)` exactly as today; `CancellableBrainCall.cancel()` already calls `raw_stream.close()` — now that closes the socket. Both streaming entry points (`_chat_llamacpp` stream branch at `:267` and `start_cancellable_chat` at `:443`) route through `_start_llamacpp_stream`, so both gain the socket transport. The non-streaming buffered `_chat_llamacpp` completion (openai client) is untouched.

### Captured wire format (the parser's ground truth)

```
HTTP/1.1 200 OK\r\nConnection: close\r\nContent-Type: text/event-stream\r\n
Server: llama.cpp\r\nTransfer-Encoding: chunked\r\n...\r\n\r\n
1f7\r\ndata: {"choices":[{"delta":{"role":"assistant","content":null}}],...}\n\n
data: {"choices":[{"delta":{"content":"OK"}}],...}\n\n\r\n
1dc\r\ndata: {"choices":[{"finish_reason":"stop","delta":{}},...]}\n\n\r\n
e\r\ndata: [DONE]\n\n\r\n0\r\n\r\n
```

Note: a single chunk may carry multiple `data:` events; `delta.content` may be `null` (skip); the final `data:` before `[DONE]` carries a `timings` block (ignored — not content).

## 3. What stays exactly as built (do NOT touch)

- `BrainGateway`, `BrainPurpose` closed enum, derived priority, `_reserve_slot` preemption loop.
- `CancellableBrainCall` (idempotent cross-thread cancel; converts close-induced iteration error → `BrainPreempted`).
- `BrainPreempted` as a distinct exception caught before the daemon's generic retry + every broad except on the cycle/owner chains.
- Content-free telemetry (`brain_gateway_event`) **and** the `brain_gateway_preempt_probe` diagnostic + witnessed schema evolution from F2 commit `32e9c01` — **kept** (cherry-picked), not re-derived.
- No-bypass invariant.

## 4. Invariants / covenant

- **Content-free** — no prompt/reply/token text in any telemetry; the transport logs nothing content-bearing.
- **Cancelled cognition reschedules, not deleted** — a preempted cycle yields `BrainPreempted`, stores no partial thought, triggers no false retry. Maez's inner life is interrupted, not thinned.
- **Brain-agnostic, substrate-side** — transport plumbing only; no change to the brain's grammar.
- **Recall stays OFF** — this slice ends at a proven forced-collision release; the recall default-on re-gate is a separate owner-run step afterward.

## 5. Acceptance gate (owner-run, adjusted per owner)

Forced collision: background cycle in-flight, foreground `owner_recall` fires →
- **background socket abort releases the slot within ~1.5s** (the measured physical abort is ~1.2s; the bar is ~1.5s, NOT sub-second — do not fail a solved problem by 200ms),
- background `preempted=True`, **no `preempt_timeout`**, no retry, no partial store,
- full six-prompt smoke **p95 stays under the A7 ceiling**, Maez voice + inner-life cadence intact.

Any miss keeps recall off.

## 6. Testing & process

- **unittest** (`.venv/bin/python -m unittest`), **NO pytest**.
- **Hermetic Stage-0:** a fake socket replaying the captured bytes proves the parser yields the right tokens; a fake socket that blocks before yielding bytes proves the handle (and `close()`) exist before iteration and that cross-thread `close()` unblocks iteration → `BrainPreempted`. Byte-equivalence: socket-parsed buffered reply == prior path for the same event sequence.
- **Fragmentation tests are MANDATORY.** The fake socket must split bytes across multiple `recv()` calls at adversarial boundaries — mid status line, mid header, between chunk-size line and chunk body, mid-CRLF, and mid `data: {json}\n\n` — because TCP does not preserve the captured frame boundaries. The parser must be a stateful incremental reader (a buffer that accumulates across `recv()`s), NOT a `recv()`-returns-a-whole-line assumption. Include a `recv()`-returns-1-byte-at-a-time torture case.
- **Strictness tests:** non-200 → `BackendError`; malformed chunk size / bad framing without cancel → `BackendError`; empty stream (`[DONE]`, zero content) without cancel → `BackendError`; truncation *after* `close()` → clean stop → `BrainPreempted` (no `BackendError`, no retry); `https` base URL → `BackendError`.
- **Owner-run live gate:** the forced-collision §5 procedure (separate note, not a unit test — touches live llama-server).
- **Floor both directions** on a clean checkout (NOT git stash); known-unrelated flaky trio (egress / web-slice / import-shim) excluded by name.
- **Branch hygiene:** new branch off `main`; **cherry-pick F2's `32e9c01`** (gateway preempt-probe diagnostic) so the good part is reused; the F2 branch (`brain-gateway-preempt-effectiveness`) stays unmerged and is later deleted/closed.

## 7. Non-goals

- **No second slot / `--parallel 2`** (mid-eval preemption is achievable on one slot).
- **No MTP** (later headroom, not the cure).
- **No httpx / requests transport** (both hide the fd until post-eval — proven).
- **No recall default-on flip** (separate owner-run step after the gate passes).
- **No change to the gateway/priority/exception structure** (transport-only slice).
