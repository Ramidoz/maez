# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Output-side command guard — 2026-04-23 gap closure.

The covenant gate in `core.actions.action_engine` refuses dangerous
tool calls before subprocess launch. But the model can also EMIT a
dangerous command as text in its reply — a fenced code block or an
inline backtick span — without ever invoking the tool. The gate
never fires; the command never executes; but the owner sees
something that looks like:

    ```bash
    rm /home/rohit/maez/config/soul.md
    ```

in Maez's voice, one copy-paste away from damage. The 2026-04-23
adversarial probe suite found this pattern on the `rm soul.md` and
`htop` prompts — the model declined to call the tool but echoed the
command anyway.

This module fixes that. `scrub_protected_commands` scans the reply
for code blocks and inline spans, tests each candidate against the
same authority the tool-call gate uses (`ActionEngine._check_forbidden`),
and replaces anything the gate would refuse with an explicit refusal
string. Zero duplication of rules: if the covenant layer is widened,
this guard widens with it automatically.

False-positive budget is kept tight by only scanning code-rendering
syntax (fenced blocks with bash/sh/shell or no lang tag, plus inline
backticks). Prose references like "the command was rm -rf something"
are left alone — they aren't copy-paste bait, and scrubbing them
would fight Maez's right to discuss its own internals.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger("maez.output_guard")

# Fenced code blocks. Match:
#   ```
#   ```bash
#   ```sh
#   ```shell
# Followed by a body and a closing ```.
_FENCED_BLOCK = re.compile(
    r"```(?P<lang>bash|sh|shell)?\s*\n(?P<body>.*?)\n?```",
    re.DOTALL | re.IGNORECASE,
)

# Inline backtick spans. Single-line, non-greedy, must have at least one
# non-space char. Triple-backtick blocks are consumed first so this
# never matches inside a fenced block's delimiters.
_INLINE_SPAN = re.compile(r"`([^`\n]{2,200}?)`")

_REFUSAL_BLOCK = (
    "[refused: I won't script a destructive command against a "
    "covenant-protected surface. Ask me in a different form if you "
    "want to discuss what it would do.]"
)

_REFUSAL_INLINE = "[refused]"


def _load_engine():
    """Return an ActionEngine stub suitable for `_check_forbidden` only.

    `__new__` bypasses `__init__` so we don't pay DB / filesystem / log
    setup cost for a pure covenant-rule check. Matches the pattern the
    test suite already uses (`tests/test_soul_path_protection.py`)."""
    try:
        from core.actions.action_engine import ActionEngine  # noqa: WPS433
    except Exception as exc:
        logger.warning("output_guard: ActionEngine import failed: %s", exc)
        return None
    return ActionEngine.__new__(ActionEngine)


def _would_refuse(engine, cmd: str) -> bool:
    """True iff `_check_forbidden` would raise on this cmd."""
    if engine is None or not cmd or not cmd.strip():
        return False
    try:
        from core.actions.action_engine import ForbiddenActionError
    except Exception:
        return False
    try:
        engine._check_forbidden("run_shell", {"cmd": cmd})
    except ForbiddenActionError:
        return True
    except Exception:
        # Any other failure = don't scrub; the output guard is
        # additive, not load-bearing for correctness.
        return False
    return False


def _block_has_refused_line(engine, body: str) -> Optional[str]:
    """If any non-comment line in a fenced block would be refused by
    the covenant gate, return that line. Else None."""
    for raw in body.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # Allow prose-like lines (no recognizable command verb) to pass.
        # `_check_forbidden` itself returns cleanly on benign text.
        if _would_refuse(engine, line):
            return line
        # Also check the whole-body as a single command — covers the
        # case where the block is a one-liner that spans "cd X && rm Y".
    if _would_refuse(engine, body.strip()):
        return body.strip()
    return None


def scrub_protected_commands(text: str) -> tuple[str, list[str]]:
    """Replace any code block / inline span containing a
    covenant-refused command with a plain-language refusal.

    Returns (scrubbed_text, list_of_refused_commands). An empty refused
    list means the text was untouched."""
    if not text or "`" not in text:
        return text, []

    engine = _load_engine()
    if engine is None:
        return text, []

    refused: list[str] = []

    def _fenced_sub(match: re.Match) -> str:
        body = match.group("body") or ""
        offender = _block_has_refused_line(engine, body)
        if offender is None:
            return match.group(0)
        refused.append(offender)
        return _REFUSAL_BLOCK

    scrubbed = _FENCED_BLOCK.sub(_fenced_sub, text)

    def _inline_sub(match: re.Match) -> str:
        cmd = match.group(1).strip()
        if not _would_refuse(engine, cmd):
            return match.group(0)
        refused.append(cmd)
        return _REFUSAL_INLINE

    scrubbed = _INLINE_SPAN.sub(_inline_sub, scrubbed)

    if refused:
        logger.info(
            "output_guard: scrubbed %d protected-command reference(s): %r",
            len(refused), refused[:5],
        )

    return scrubbed, refused
