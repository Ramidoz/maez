"""Socket-level mid-eval abort probe (owner-run, decision-grade).

Question: if we close the raw client socket WHILE llama-server is mid
prompt-eval (before any response headers), does the server ABORT the slot?

Confound: the live daemon fires autonomous cognition cycles (~112K megaprompt,
~18-21s eval) that grab the single slot. So this probe distinguishes outcomes
by MAGNITUDE + a no-close control, instead of pausing Maez's cognition:

  - idle baseline (server free, tiny prompt)         ~= B   (~1s)
  - CLOSE mid-eval, then follow-up TTFB:
        ~= B            -> server ABORTED on disconnect (slot freed)
        ~= my-eval-rem  -> server did NOT abort (ran my eval to completion)
        >> that (~18s)  -> ambient daemon-cycle collision (ignore for abort q.)
  - NOCLOSE control (let my big eval run), follow-up TTFB ~= my-eval-rem (~7-8s)

If CLOSE clusters at ~B and NOCLOSE clusters at ~my-eval-rem, the close itself
freed the slot -> a socket-level cancellable transport is viable.

Content-free; unique prompts each run (defeats KV-cache); touches only the
live server (no daemon flags, no recall posture). Prints wall-clock so slow
trials can be correlated with the daemon cycle log.
"""

from __future__ import annotations

import json
import os
import socket
import time
from datetime import datetime

HOST, PORT, PATH = "127.0.0.1", 8080, "/v1/chat/completions"
MODEL = "primary-model"
FILLER = "The history of computing is long and detailed. " * 1800  # ~21k tokens


def _body(unique: str, content: str, max_tokens: int) -> bytes:
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": f"[{unique}] {content}"}],
        "temperature": 0.0,
        "max_tokens": max_tokens,
        "stream": True,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    return json.dumps(payload).encode("utf-8")


def _send(body: bytes) -> socket.socket:
    s = socket.create_connection((HOST, PORT), timeout=90)
    head = (
        f"POST {PATH} HTTP/1.1\r\n"
        f"Host: {HOST}:{PORT}\r\n"
        f"Authorization: Bearer llamacpp\r\n"
        f"Content-Type: application/json\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"Connection: close\r\n\r\n"
    ).encode("utf-8")
    s.sendall(head + body)
    return s


def _ttfb(body: bytes) -> float:
    s = _send(body)
    t0 = time.monotonic()
    s.settimeout(90)
    try:
        s.recv(64)
    finally:
        ms = (time.monotonic() - t0) * 1000.0
        s.close()
    return ms


def _now() -> str:
    return datetime.now().strftime("%H:%M:%S")


def main() -> None:
    stamp = str(os.getpid())
    base = _ttfb(_body(f"{stamp}-base", "Reply with OK.", 4))
    print(f"[{_now()}] idle_small_ttfb_ms={base:.0f}")

    for i in range(4):
        u = f"{stamp}-c{i}"
        big = _send(_body(f"{u}-big", FILLER, 8))
        time.sleep(2.0)
        big.close()                                   # ABORT mid-eval
        t = _ttfb(_body(f"{u}-after", "Reply with OK.", 4))
        print(f"[{_now()}] CLOSE   trial={i} after_ttfb_ms={t:.0f}")
        time.sleep(0.5)

    for i in range(3):
        u = f"{stamp}-n{i}"
        big = _send(_body(f"{u}-big", FILLER, 8))
        time.sleep(2.0)
        # NO close: hold the socket open so my big eval keeps the slot.
        t = _ttfb(_body(f"{u}-after", "Reply with OK.", 4))
        print(f"[{_now()}] NOCLOSE trial={i} after_ttfb_ms={t:.0f}")
        big.close()
        time.sleep(0.5)


if __name__ == "__main__":
    main()
