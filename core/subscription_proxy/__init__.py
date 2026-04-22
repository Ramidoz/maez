"""Maez subscription proxy package.

Localhost OpenAI-compatible endpoint that routes `/v1/chat/completions`
requests to pluggable backend adapters — each wrapping a specific
subscription CLI (Claude today, Gemini / others later).

Layout:
  server.py              — FastAPI app, shared budget, trajectory log,
                           request → adapter routing.
  adapters/base.py       — abstract Adapter interface every backend
                           implements.
  adapters/claude_cli.py — wraps `claude --print` (Claude Max subscription).

  Future stubs documented in adapters/_PROVIDERS.md — add a new file +
  register it in server.ADAPTERS and nothing else needs to change.

Entry: `python -m core.subscription_proxy` starts the server on
127.0.0.1:11438 by default.
"""
from core.subscription_proxy.server import app  # noqa: F401
