"""The silent organ substitution, made visible.

Full-body audit 2026-08-14: when run_brain_loop raised, inbound_core set
brain_failed=True and the turn proceeded on the LEGACY pre-triad recall
with nothing but a generic warning -- an older organ silently swapped in.
These tests pin the honesty seam: the daemon records the downgrade as
visible state, and inbound_core actually forwards the fact.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[1]


def test_note_recall_downgrade_records_visible_state(caplog):
    import logging

    # The "maez" logger deliberately does not propagate to root (the
    # surface-v2 runner owns root), so caplog's root handler never sees
    # it; attach the capture handler to the logger directly.
    from daemon.maez_daemon import MaezDaemon

    holder = SimpleNamespace()
    maez_logger = logging.getLogger("maez")
    maez_logger.addHandler(caplog.handler)
    try:
        with caplog.at_level("WARNING", logger="maez"):
            MaezDaemon._note_recall_downgrade(
                holder, source="telegram_surface", reason="brain_loop_exception"
            )
    finally:
        maez_logger.removeHandler(caplog.handler)

    note = holder._last_recall_downgrade
    assert note["schema"] == "recall_downgrade.v0"
    assert note["source"] == "telegram_surface"
    assert note["reason"] == "brain_loop_exception"
    assert note["at_ts"] > 0
    joined = " ".join(record.getMessage() for record in caplog.records)
    assert "recall_mode_downgrade" in joined
    assert "served_by=legacy_pre_triad" in joined
    assert "telegram_surface" in joined


def test_handle_message_accepts_and_uses_brain_failed():
    source = (REPO / "daemon" / "maez_daemon.py").read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "handle_message":
            kwonly = {a.arg for a in node.args.kwonlyargs}
            assert "brain_failed" in kwonly
            body_src = ast.get_source_segment(source, node)
            assert "_note_recall_downgrade" in body_src
            return
    raise AssertionError("handle_message not found")


def test_inbound_core_forwards_brain_failed():
    source = (REPO / "daemon" / "inbound_core.py").read_text()
    call = re.search(
        r"daemon\.handle_message\((?:[^()]|\([^()]*\))*\)", source, re.S
    )
    assert call is not None, "handle_message call site not found"
    assert "brain_failed=brain_failed" in call.group(0)
