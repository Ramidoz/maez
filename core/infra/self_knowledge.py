# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Self-knowledge — Maez's introspection of its own hardware and
loaded model state.

Step 0 of the Decision-19/20 capability-acquisition pipeline arc.
Maez has to know its own VRAM, context window, and loaded model
to evaluate capability candidates against its own constraints
("don't propose a 1T-parameter model into 24GB VRAM"). Without
this module, the self-evaluator stage of the pipeline can't fire.

Design rules:

- **Failures return None, not exceptions.** If nvidia-smi isn't
  installed, or llama-server isn't running, or the response is
  malformed, the public function returns None and the caller
  decides what to do. Self-knowledge is best-effort by definition;
  raising would make the pipeline brittle when one probe fails.
- **No external dependencies.** Uses subprocess + urllib only.
  Avoids pynvml/pycuda/torch which would inflate the install
  footprint for a self-introspection module.
- **Conservative on uncertainty.** ``can_fit_in_vram_mb`` returns
  False when VRAM is unknown. A candidate Maez can't verify
  fitting should be deferred, not optimistically proposed.

Public surface:

  vram_total_mb()           int | None
  vram_available_mb()       int | None
  gpu_name()                str | None
  loaded_model_name()       str | None
  current_context_window()  int | None
  can_fit_in_vram_mb(n)     bool
  summarize()               dict — diagnostic / cockpit-friendly view
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)


# ── nvidia-smi probe ───────────────────────────────────────────────


_NVIDIA_SMI_CMD = (
    "nvidia-smi",
    "--query-gpu=name,memory.total,memory.free",
    "--format=csv,noheader",
)
_NVIDIA_SMI_TIMEOUT_S = 3.0
# Force C locale so nvidia-smi emits ASCII-comma-free numbers.
# Some locales render "24,564 MiB" which would silently parse as
# 24 without the locale guard. (Audit fix, 2026-04-30.)
_NVIDIA_SMI_ENV: dict[str, str] = {
    **os.environ, "LC_ALL": "C", "LANG": "C",
}


def _parse_nvidia_smi_query(stdout: str) -> dict | None:
    """Parse the CSV nvidia-smi output. First GPU only — multi-GPU
    Maez isn't a v1 case. Returns None on garbage rather than
    raising, so the public API can fall through to None."""
    if not stdout or not stdout.strip():
        return None
    line = stdout.strip().splitlines()[0]
    parts = [p.strip() for p in line.split(",")]
    if len(parts) < 3:
        return None
    name = parts[0]
    if not name:
        return None
    # Memory values look like "24564 MiB" or "24564MiB" depending
    # on driver version. Strip non-digit suffix. Comma-separated
    # numbers ("24,564 MiB") should be normalized first because the
    # subprocess call sets LC_ALL=C, but a defensive strip costs
    # nothing and survives a future locale-leak regression.
    def _mb(s: str) -> int | None:
        s = s.replace(",", "")
        m = re.match(r"\s*(\d+)", s)
        return int(m.group(1)) if m else None

    total = _mb(parts[1])
    avail = _mb(parts[2])
    if total is None or avail is None:
        return None
    return {"name": name, "total_mb": total, "available_mb": avail}


def _run_nvidia_smi() -> dict | None:
    """Best-effort: call nvidia-smi, parse, return dict or None.

    LC_ALL=C is forced to suppress locale-specific number formatting
    (would parse "24,564 MiB" as 24).
    """
    try:
        result = subprocess.run(
            _NVIDIA_SMI_CMD,
            capture_output=True, text=True,
            timeout=_NVIDIA_SMI_TIMEOUT_S, check=False,
            env=_NVIDIA_SMI_ENV,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired,
            OSError) as e:
        logger.debug("self_knowledge: nvidia-smi probe failed: %s", e)
        return None
    if result.returncode != 0:
        logger.debug(
            "self_knowledge: nvidia-smi exit=%d stderr=%r",
            result.returncode, (result.stderr or "")[:200],
        )
        return None
    return _parse_nvidia_smi_query(result.stdout or "")


def vram_total_mb() -> int | None:
    """Total VRAM on the (first) GPU in megabytes. None on probe
    failure."""
    info = _run_nvidia_smi()
    return info["total_mb"] if info else None


def vram_available_mb() -> int | None:
    """Currently-free VRAM in megabytes. None on probe failure."""
    info = _run_nvidia_smi()
    return info["available_mb"] if info else None


def gpu_name() -> str | None:
    """GPU name as nvidia-smi reports it (e.g. 'NVIDIA GeForce
    RTX 4090'). None on probe failure."""
    info = _run_nvidia_smi()
    return info["name"] if info else None


# ── llama-server probe ─────────────────────────────────────────────


def _llama_models_url() -> str:
    """Resolve the /v1/models endpoint. Reads PRIMARY_BASE_URL from
    core.routing.model_config so model-server URL changes are config-
    driven, not edits to this file. Imports lazily so a misconfigured
    model_config doesn't make this whole module unimportable."""
    try:
        from core.routing.model_config import PRIMARY_BASE_URL
        base = PRIMARY_BASE_URL.rstrip("/")
    except Exception:  # pragma: no cover — defensive
        base = "http://127.0.0.1:8080"
    return f"{base}/v1/models"


_LLAMA_TIMEOUT_S = 3.0


def _fetch_models_payload() -> dict | None:
    """Pull the /v1/models payload from llama-server. Returns the
    parsed dict or None on any failure (server down, bad JSON,
    timeout). URL is resolved through ``core.routing.model_config``
    so model-server endpoint changes are config-driven."""
    try:
        with urllib.request.urlopen(
            _llama_models_url(), timeout=_LLAMA_TIMEOUT_S,
        ) as resp:
            return json.load(resp)
    except (urllib.error.URLError, OSError,
            json.JSONDecodeError, ValueError) as e:
        logger.debug(
            "self_knowledge: llama-server /v1/models probe failed: %s", e,
        )
        return None


def loaded_model_name() -> str | None:
    """Name of the model currently loaded by llama-server. Prefers
    OpenAI-canonical ``data[].id`` (the standard since 2024); falls
    back to llama-server's legacy ``models[].name``."""
    payload = _fetch_models_payload()
    if not isinstance(payload, dict):
        return None
    data = payload.get("data") or []
    if data and isinstance(data[0], dict) and data[0].get("id"):
        return str(data[0]["id"])
    models = payload.get("models") or []
    if models and isinstance(models[0], dict) and models[0].get("name"):
        return str(models[0]["name"])
    return None


def current_context_window() -> int | None:
    """Context window of the loaded model, in tokens. Read from
    llama-server's ``data[].meta.n_ctx_train``. None on probe
    failure or missing field."""
    payload = _fetch_models_payload()
    if not isinstance(payload, dict):
        return None
    data = payload.get("data") or []
    if not data or not isinstance(data[0], dict):
        return None
    meta = data[0].get("meta") or {}
    n_ctx = meta.get("n_ctx_train")
    if isinstance(n_ctx, int) and n_ctx > 0:
        return n_ctx
    return None


# ── headroom helpers ───────────────────────────────────────────────


def can_fit_in_vram_mb(needed_mb: int) -> bool:
    """Return True iff Maez has at least ``needed_mb`` of VRAM
    available right now. **False on uncertainty** — if VRAM can't
    be probed, treat as "won't fit" so the self-evaluator defers
    rather than optimistically proposing."""
    avail = vram_available_mb()
    if avail is None:
        return False
    return avail >= needed_mb


# ── diagnostic summary ─────────────────────────────────────────────


def summarize() -> dict:
    """Compact dict the cockpit / capability-pipeline self-evaluator
    can consume. Fields with failed probes are None; the dict shape
    is stable.

    Calls each probe at most once (one nvidia-smi invocation, one
    /v1/models fetch) — naive composition of the public functions
    would multiply both. (Audit fix, 2026-04-30.)
    """
    nv = _run_nvidia_smi()
    payload = _fetch_models_payload()

    name = None
    ctx = None
    if isinstance(payload, dict):
        data = payload.get("data") or []
        if data and isinstance(data[0], dict):
            d0 = data[0]
            if d0.get("id"):
                name = str(d0["id"])
            meta = d0.get("meta") or {}
            n_ctx = meta.get("n_ctx_train")
            if isinstance(n_ctx, int) and n_ctx > 0:
                ctx = n_ctx
        if name is None:
            models = payload.get("models") or []
            if models and isinstance(models[0], dict) and models[0].get("name"):
                name = str(models[0]["name"])

    return {
        "vram_total_mb": nv["total_mb"] if nv else None,
        "vram_available_mb": nv["available_mb"] if nv else None,
        "gpu_name": nv["name"] if nv else None,
        "loaded_model_name": name,
        "current_context_window": ctx,
    }


__all__ = [
    "can_fit_in_vram_mb",
    "current_context_window",
    "gpu_name",
    "loaded_model_name",
    "summarize",
    "vram_available_mb",
    "vram_total_mb",
]
