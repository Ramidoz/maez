# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""error_classifier.py — structured taxonomy for LLM backend errors.

Borrowed 2026-04-21 from hermes-agent's error_classifier (MIT), scoped
down to Maez's actual error surface. Hermes's 830-line version is 90%
cloud-API specific (Anthropic thinking sigs, OpenRouter wrapping,
billing patterns, credential rotation). Maez runs local llama.cpp with
Ollama fallback — very different failure modes.

Scope (narrow on purpose):
  Classifies errors raised by llm_client.chat() and its callers into a
  small set of categories with structured recovery hints. Does NOT change
  _reason()'s retry/fallback behavior. Observational: the classifier's
  output is emitted as one line to cognition.log so the cockpit (and
  anyone tailing the log) can see WHICH class of error is happening.

  Behavior-level routing (e.g. "on context_overflow, drop older recall
  chunks and retry") is a follow-up that should only land once baseline
  cycle stability is observed to be unaffected. This commit lands the
  taxonomy and the telemetry — not the routing.

Maez's actual error surface (from grepping and GPU OOM observed earlier
this session):

  ConnectionRefusedError / urllib / httpx connect errors
      → llama-server is down or restarting. Retryable after wait.

  Read/socket timeout
      → model is hung or GPU is saturated. Retryable.

  "cuda_malloc failed" / "out of memory" in log
      → GPU VRAM pressure. Structural — more RAM or smaller model.

  "exceeds the max_model_len" / "n_ctx_slot" / "context length"
      → prompt too large for the server's ctx-size. Compress-able.

  "ollama.ResponseError" / "failed to pull model"
      → Ollama-backend issues. Switch backend or retry.

  JSON decode / parse errors on response
      → model output was corrupted. Log, don't retry the same prompt.

Fail-SAFE: if the classifier can't identify the error, returns
ErrorClass.unknown with retryable=True and no compression hint. Caller
treats it the same as today's bare `except Exception`.
"""
from __future__ import annotations

import enum
import logging
from dataclasses import dataclass

logger = logging.getLogger("maez.error_classifier")
_cog_logger = logging.getLogger("maez.cognition")

# Ensure cognition.log FileHandler is attached. Daemon gets this for free
# via core.cognition_quality at startup; this module may be imported by
# other surfaces.
try:
    from core import cognition_quality as _cog_quality_bootstrap  # noqa: F401
except Exception:
    pass


# ── taxonomy ───────────────────────────────────────────────────────────

class ErrorClass(enum.Enum):
    """Category of backend error for recovery routing."""

    # Transport layer
    backend_down = "backend_down"            # connection refused, not listening
    backend_timeout = "backend_timeout"      # read/connect timeout (model hung)

    # GPU resource
    gpu_oom = "gpu_oom"                      # cudaMalloc failed, CUDA OOM

    # Prompt / context
    context_overflow = "context_overflow"    # prompt exceeds backend ctx-size

    # Model artifacts
    model_missing = "model_missing"          # model file or alias not found

    # Response parsing
    response_malformed = "response_malformed"  # invalid JSON, empty content, corrupted

    # Catch-all
    unknown = "unknown"


# ── classification result ─────────────────────────────────────────────

@dataclass(frozen=True)
class ClassifiedError:
    """Structured classification with recovery hints. Callers read the
    hint flags rather than re-classifying the error themselves."""

    error_class: ErrorClass
    message: str = ""
    # Recovery hints — advisory. Observational layer doesn't act on these
    # automatically; a future behavior layer can route on them.
    retryable: bool = True
    likely_transient: bool = False    # true-flash errors that usually self-resolve
    likely_structural: bool = False   # needs operator intervention (OOM, missing model)
    should_compress_prompt: bool = False  # context_overflow / payload-too-large


# ── pattern banks ─────────────────────────────────────────────────────

# Substring patterns (lowercased) mapped to ErrorClass. Patterns are
# intentionally narrow — a hit must be specific enough that a false
# positive is unlikely. Anything that doesn't hit falls through to
# ErrorClass.unknown.

_GPU_OOM_PATTERNS = (
    "cudamalloc failed",      # "cudaMalloc failed: out of memory" (observed in real logs)
    "cuda_malloc failed",
    "cuda error: out of memory",
    "cudaoutofmemoryerror",
    "cuda out of memory",
    "ggml_backend_cuda_buffer_type_alloc_buffer",
    "alloc_tensor_range: failed to allocate cuda",
)

_CONTEXT_OVERFLOW_PATTERNS = (
    "exceeds the max_model_len",
    "max_model_len",
    "n_ctx_slot",
    "slot context",
    "context length exceeded",
    "context size has been exceeded",
    "maximum context length",
    "prompt is too long",
    "prompt exceeds max length",
    "prompt length",
    "input is too long",
    "maximum number of tokens",
    "token limit",
)

_BACKEND_DOWN_PATTERNS = (
    "connection refused",
    "connectionrefusederror",
    "failed to establish a new connection",
    "no route to host",
    "nameresolutionerror",
    "cannot connect to host",
)

_BACKEND_TIMEOUT_PATTERNS = (
    "read timed out",
    "connection timed out",
    "readtimeout",
    "connecttimeout",
    "pooltimeout",
    "request timed out",
    "response_timeout",
)

_MODEL_MISSING_PATTERNS = (
    "model not found",
    "model_not_found",
    "no such model",
    "failed to pull model",
    "model does not exist",
    "unknown model",
    "unsupported model",
)

_RESPONSE_MALFORMED_PATTERNS = (
    "expecting value",                 # json.JSONDecodeError template
    "json decode",
    "jsondecodeerror",
    "invalid json",
    "empty response",
    "unterminated string",
)

# Transport error type names that map to backend_timeout without string match.
_TIMEOUT_ERROR_TYPES = frozenset({
    "ReadTimeout", "ConnectTimeout", "PoolTimeout",
    "TimeoutError", "APITimeoutError",
})

# Transport error type names that map to backend_down.
_CONNECT_ERROR_TYPES = frozenset({
    "ConnectError", "ConnectionError", "ConnectionRefusedError",
    "ConnectionAbortedError", "ConnectionResetError",
    "APIConnectionError",
})


# ── classifier ────────────────────────────────────────────────────────

def classify(error: Exception) -> ClassifiedError:
    """Classify an exception from llm_client.chat() or similar. Never raises.

    Caller usage:
        try:
            resp = _llm_client.chat(...)
        except Exception as e:
            classified = classify(e)
            emit_telemetry(classified, surface="daemon_cycle")
            # ...existing error handling unchanged for now...
    """
    msg = (str(error) or "").lower()
    error_type = type(error).__name__

    # Exception-type fast paths — these are unambiguous.
    if error_type in _TIMEOUT_ERROR_TYPES or isinstance(error, TimeoutError):
        return ClassifiedError(
            error_class=ErrorClass.backend_timeout,
            message=_short_message(error),
            retryable=True,
            likely_transient=True,
        )
    if error_type in _CONNECT_ERROR_TYPES or isinstance(error, ConnectionError):
        return ClassifiedError(
            error_class=ErrorClass.backend_down,
            message=_short_message(error),
            retryable=True,
            likely_transient=True,
        )

    # Substring matching: priority-ordered so specific patterns win.
    if _any_in(msg, _GPU_OOM_PATTERNS):
        return ClassifiedError(
            error_class=ErrorClass.gpu_oom,
            message=_short_message(error),
            retryable=False,
            likely_structural=True,
        )
    if _any_in(msg, _CONTEXT_OVERFLOW_PATTERNS):
        return ClassifiedError(
            error_class=ErrorClass.context_overflow,
            message=_short_message(error),
            retryable=True,
            should_compress_prompt=True,
        )
    if _any_in(msg, _MODEL_MISSING_PATTERNS):
        return ClassifiedError(
            error_class=ErrorClass.model_missing,
            message=_short_message(error),
            retryable=False,
            likely_structural=True,
        )
    if _any_in(msg, _BACKEND_DOWN_PATTERNS):
        return ClassifiedError(
            error_class=ErrorClass.backend_down,
            message=_short_message(error),
            retryable=True,
            likely_transient=True,
        )
    if _any_in(msg, _BACKEND_TIMEOUT_PATTERNS):
        return ClassifiedError(
            error_class=ErrorClass.backend_timeout,
            message=_short_message(error),
            retryable=True,
            likely_transient=True,
        )
    if _any_in(msg, _RESPONSE_MALFORMED_PATTERNS):
        return ClassifiedError(
            error_class=ErrorClass.response_malformed,
            message=_short_message(error),
            retryable=False,  # same prompt will likely produce same bad output
        )

    # Fallback — unknown, retryable. Behavior identical to current
    # bare `except Exception` path.
    return ClassifiedError(
        error_class=ErrorClass.unknown,
        message=_short_message(error),
        retryable=True,
    )


def emit_telemetry(
    classified: ClassifiedError,
    *,
    surface: str = "unknown",
) -> None:
    """Write one structured line to cognition.log for the cockpit and
    log-greppers. Shape is stable — the cockpit parses this.

        error_classifier | surface=<s> class=<k> retryable=<0|1> transient=<0|1>
                         | structural=<0|1> compress=<0|1> msg="<short>"

    Does NOT include stack traces — callers should still logger.exception
    on unknown classifications so debugging information isn't lost.
    """
    _cog_logger.info(
        "error_classifier | surface=%s class=%s retryable=%d transient=%d "
        "structural=%d compress=%d msg=%r",
        surface,
        classified.error_class.value,
        int(classified.retryable),
        int(classified.likely_transient),
        int(classified.likely_structural),
        int(classified.should_compress_prompt),
        (classified.message or "")[:200],
    )


def owner_visible_message(classified: ClassifiedError) -> str:
    """Short owner-facing text for backend failures.

    Logs keep the raw exception. Surfaces should not show transport
    wrappers, HTTP status payloads, or llama.cpp server internals to Rohit.
    """
    if classified.error_class is ErrorClass.context_overflow:
        return (
            "I hit the local brain's context limit while answering. "
            "Try me again in a moment."
        )
    if classified.error_class is ErrorClass.backend_down:
        return (
            "My local brain is still waking or restarting. "
            "Try me again in a moment."
        )
    if classified.error_class is ErrorClass.backend_timeout:
        return (
            "My local brain is taking too long to answer. "
            "Try me again in a moment."
        )
    if classified.error_class is ErrorClass.gpu_oom:
        return (
            "My local brain ran out of GPU room while answering. "
            "I need the local model stack checked."
        )
    if classified.error_class is ErrorClass.model_missing:
        return (
            "I cannot find the local model I need to answer. "
            "The model stack needs checking."
        )
    return "I hit a local brain error while answering. Try me again in a moment."


# ── helpers ───────────────────────────────────────────────────────────

def _any_in(haystack: str, needles) -> bool:
    return any(n in haystack for n in needles)


def _short_message(error: Exception) -> str:
    """First line of the error, trimmed. Error payloads can be massive
    (stack traces, log dumps); we only want a human-readable identifier."""
    s = str(error) or ""
    first_line = s.splitlines()[0] if s else ""
    return first_line[:300]


# ── diagnostics ───────────────────────────────────────────────────────

def _diag_class_names() -> tuple[str, ...]:
    """Test helper — enumerate the error class values."""
    return tuple(c.value for c in ErrorClass)
