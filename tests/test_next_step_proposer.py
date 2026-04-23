# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""
Tests for ConversationController.propose_next_step_from_probe extraction.

Verifies that the logic moved from skills/telegram_voice.py into
core/conversation_controller.py is structurally present and that the
TelegramVoice wrapper delegates correctly.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ─── Layer registration ────────────────────────────────────────────────

def test_next_step_proposer_layer_registered():
    from core.conversation_controller import ConversationController
    ctrl = ConversationController(memory=None)
    assert ctrl.has_layer("next_step_proposer")


def test_all_prior_layers_still_registered():
    from core.conversation_controller import ConversationController
    ctrl = ConversationController(memory=None)
    for layer in ("honesty", "pending_card_view", "narration_check",
                  "offer_binding", "next_step_parse", "next_step_proposer"):
        assert ctrl.has_layer(layer), f"layer {layer!r} missing"


# ─── _get_pipeline helper ──────────────────────────────────────────────

def test_get_pipeline_returns_none_when_no_pipeline():
    from core.conversation_controller import ConversationController
    ctrl = ConversationController(memory=None)
    assert ctrl._get_pipeline() is None


def test_get_pipeline_uses_pipeline_getter():
    from core.conversation_controller import ConversationController

    class FakePipe:
        pass

    fake = FakePipe()
    ctrl = ConversationController(memory=None, pipeline_getter=lambda: fake)
    assert ctrl._get_pipeline() is fake


def test_get_pipeline_returns_direct_pipeline():
    from core.conversation_controller import ConversationController

    class FakePipe:
        pass

    fake = FakePipe()
    ctrl = ConversationController(memory=None, pipeline=fake)
    assert ctrl._get_pipeline() is fake


def test_get_pipeline_prefers_direct_over_getter():
    from core.conversation_controller import ConversationController

    class FakePipe:
        pass

    direct = FakePipe()
    getter_result = FakePipe()
    ctrl = ConversationController(
        memory=None, pipeline=direct, pipeline_getter=lambda: getter_result
    )
    assert ctrl._get_pipeline() is direct


# ─── propose_next_step_from_probe: no-probe path ──────────────────────

def test_propose_skips_when_no_probe_in_db(tmp_path):
    """With an empty audit_log.db the method returns kind='skipped'."""
    import sqlite3
    from core.conversation_controller import ConversationController

    db = tmp_path / "audit_log.db"
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE audit_log "
        "(ts REAL, action TEXT, params_json TEXT, outcome TEXT, outcome_notes TEXT)"
    )
    conn.commit()
    conn.close()

    ctrl = ConversationController(memory=None)
    result = ctrl.propose_next_step_from_probe(
        "figure out how to install openrgb",
        channel="telegram_text",
        chat_id="12345",
        audit_db_path=str(db),
    )
    assert result is not None
    assert result["kind"] == "skipped"


def test_propose_skips_when_probes_too_old(tmp_path):
    """Probes older than 60 s are excluded → kind='skipped'."""
    import sqlite3
    import time
    from core.conversation_controller import ConversationController

    db = tmp_path / "audit_log.db"
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE audit_log "
        "(ts REAL, action TEXT, params_json TEXT, outcome TEXT, outcome_notes TEXT)"
    )
    old_ts = time.time() - 120
    conn.execute(
        "INSERT INTO audit_log VALUES (?, ?, ?, ?, ?)",
        (old_ts, "run_shell", '{"cmd":"lsusb"}', "approved_and_ran", "Bus 001 Device 001"),
    )
    conn.commit()
    conn.close()

    ctrl = ConversationController(memory=None)
    result = ctrl.propose_next_step_from_probe(
        "figure out how to install openrgb",
        channel="telegram_text",
        chat_id="12345",
        audit_db_path=str(db),
    )
    assert result is not None
    assert result["kind"] == "skipped"


def test_propose_skips_failed_probe_with_short_notes(tmp_path):
    """Failed probe with <=30 char notes is excluded → kind='skipped'."""
    import sqlite3
    import time
    from core.conversation_controller import ConversationController

    db = tmp_path / "audit_log.db"
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE audit_log "
        "(ts REAL, action TEXT, params_json TEXT, outcome TEXT, outcome_notes TEXT)"
    )
    conn.execute(
        "INSERT INTO audit_log VALUES (?, ?, ?, ?, ?)",
        (time.time() - 5, "run_shell", '{"cmd":"grep foo /tmp"}',
         "approved_and_failed", "exit=1"),
    )
    conn.commit()
    conn.close()

    ctrl = ConversationController(memory=None)
    result = ctrl.propose_next_step_from_probe(
        "find foo",
        channel="telegram_text",
        chat_id="12345",
        audit_db_path=str(db),
    )
    assert result is not None
    assert result["kind"] == "skipped"


# ─── propose_next_step_from_probe: LLM failure path ───────────────────

def test_propose_returns_none_on_llm_failure(tmp_path):
    """LLM call failure → None (caller treats as graceful skip)."""
    import sqlite3
    import time
    from core.conversation_controller import ConversationController
    import unittest.mock as mock

    db = tmp_path / "audit_log.db"
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE audit_log "
        "(ts REAL, action TEXT, params_json TEXT, outcome TEXT, outcome_notes TEXT)"
    )
    conn.execute(
        "INSERT INTO audit_log VALUES (?, ?, ?, ?, ?)",
        (time.time() - 5, "run_shell", '{"cmd":"lsusb"}',
         "approved_and_ran",
         "Bus 001 Device 002: ID 187c:0550 Alienware LED controller"),
    )
    conn.commit()
    conn.close()

    ctrl = ConversationController(memory=None)
    with mock.patch("core.llm_client.chat", side_effect=RuntimeError("LLM down")):
        result = ctrl.propose_next_step_from_probe(
            "figure out how to control the LED",
            channel="telegram_text",
            chat_id="12345",
            audit_db_path=str(db),
        )
    assert result is None


# ─── propose_next_step_from_probe: parse→none path ────────────────────

def test_propose_returns_none_kind_when_llm_says_none(tmp_path):
    """LLM emitting 'NEXT_STEP: none' → kind='none'."""
    import sqlite3
    import time
    from core.conversation_controller import ConversationController
    import unittest.mock as mock

    db = tmp_path / "audit_log.db"
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE audit_log "
        "(ts REAL, action TEXT, params_json TEXT, outcome TEXT, outcome_notes TEXT)"
    )
    conn.execute(
        "INSERT INTO audit_log VALUES (?, ?, ?, ?, ?)",
        (time.time() - 5, "run_shell", '{"cmd":"lsusb"}',
         "approved_and_ran", "Bus 001 Device 002: ID 187c:0550 Alienware"),
    )
    conn.commit()
    conn.close()

    class FakeResp:
        class message:
            content = "NEXT_STEP: none"

    ctrl = ConversationController(memory=None)
    with mock.patch("core.llm_client.chat", return_value=FakeResp()):
        result = ctrl.propose_next_step_from_probe(
            "tell me what USB devices are connected",
            channel="telegram_text",
            chat_id="12345",
            audit_db_path=str(db),
        )
    assert result is not None
    assert result["kind"] == "none"


# ─── propose_next_step_from_probe: pipeline unavailable path ──────────

def test_propose_returns_none_kind_when_no_pipeline(tmp_path):
    """With no pipeline, kind='none' after successful LLM parse."""
    import sqlite3
    import time
    from core.conversation_controller import ConversationController
    import unittest.mock as mock

    db = tmp_path / "audit_log.db"
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE audit_log "
        "(ts REAL, action TEXT, params_json TEXT, outcome TEXT, outcome_notes TEXT)"
    )
    conn.execute(
        "INSERT INTO audit_log VALUES (?, ?, ?, ?, ?)",
        (time.time() - 5, "run_shell", '{"cmd":"lsusb"}',
         "approved_and_ran", "Bus 001 Device 002: ID 187c:0550 Alienware"),
    )
    conn.commit()
    conn.close()

    class FakeResp:
        class message:
            content = "NEXT_STEP: sudo apt install -y openrgb"

    ctrl = ConversationController(memory=None)
    with mock.patch("core.llm_client.chat", return_value=FakeResp()):
        result = ctrl.propose_next_step_from_probe(
            "figure out how to control the LED",
            channel="telegram_text",
            chat_id="12345",
            audit_db_path=str(db),
        )
    assert result is not None
    assert result["kind"] == "none"
    assert "pipeline" in result["summary"]


# ─── TelegramVoice delegation (static source inspection) ──────────────
# telegram_voice.py requires ollama which isn't available in test env.
# Use raw source read + ast to verify the delegation shape without import.

def _get_tv_method_src() -> str:
    """Extract source lines of _propose_next_step_from_probe from
    telegram_voice.py without importing the module."""
    import ast, os
    tv_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "skills", "telegram_voice.py",
    )
    with open(tv_path) as f:
        src = f.read()
    tree = ast.parse(src)
    lines = src.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "TelegramVoice":
            for item in ast.walk(node):
                if (isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and item.name == "_propose_next_step_from_probe"):
                    start = item.lineno - 1
                    end = item.end_lineno
                    return "\n".join(lines[start:end])
    raise AssertionError("_propose_next_step_from_probe not found in TelegramVoice")


def test_telegram_voice_delegation_present():
    """_propose_next_step_from_probe in TelegramVoice must delegate to
    controller, not contain its own LLM or sqlite logic."""
    src = _get_tv_method_src()
    assert "self._controller.propose_next_step_from_probe" in src
    assert "sqlite3.connect" not in src
    assert "llm_client.chat" not in src


def test_telegram_voice_delegation_passes_channel():
    """Delegation must pass channel='telegram_text'."""
    src = _get_tv_method_src()
    assert "telegram_text" in src


def test_telegram_voice_delegation_passes_audit_db_path():
    """Delegation must forward the audit_log db_path."""
    src = _get_tv_method_src()
    assert "audit_db_path" in src


# ─── main ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import tempfile
    from pathlib import Path
    print("── next_step_proposer extraction tests ──\n")

    _tmp = Path(tempfile.mkdtemp())

    test_next_step_proposer_layer_registered()
    print("  ✓ next_step_proposer layer registered")

    test_all_prior_layers_still_registered()
    print("  ✓ all prior layers still registered (honesty, pending_card_view, narration_check, offer_binding, next_step_parse)")

    test_get_pipeline_returns_none_when_no_pipeline()
    print("  ✓ _get_pipeline returns None when no pipeline")

    test_get_pipeline_uses_pipeline_getter()
    print("  ✓ _get_pipeline uses pipeline_getter callable")

    test_get_pipeline_returns_direct_pipeline()
    print("  ✓ _get_pipeline returns direct pipeline when set")

    test_get_pipeline_prefers_direct_over_getter()
    print("  ✓ _get_pipeline prefers direct pipeline over getter")

    test_propose_skips_when_no_probe_in_db(Path(tempfile.mkdtemp()))
    print("  ✓ propose_next_step_from_probe: kind=skipped when no probes in db")

    test_propose_skips_when_probes_too_old(Path(tempfile.mkdtemp()))
    print("  ✓ propose_next_step_from_probe: kind=skipped when all probes are stale (>60s)")

    test_propose_skips_failed_probe_with_short_notes(Path(tempfile.mkdtemp()))
    print("  ✓ propose_next_step_from_probe: kind=skipped when failed probe has short notes")

    test_propose_returns_none_on_llm_failure(Path(tempfile.mkdtemp()))
    print("  ✓ propose_next_step_from_probe: None on LLM failure (graceful)")

    test_propose_returns_none_kind_when_llm_says_none(Path(tempfile.mkdtemp()))
    print("  ✓ propose_next_step_from_probe: kind=none when LLM emits NEXT_STEP: none")

    test_propose_returns_none_kind_when_no_pipeline(Path(tempfile.mkdtemp()))
    print("  ✓ propose_next_step_from_probe: kind=none when pipeline unavailable after LLM parse")

    test_telegram_voice_delegation_present()
    print("  ✓ TelegramVoice delegates to controller (no sqlite/llm in body)")

    test_telegram_voice_delegation_passes_channel()
    print("  ✓ TelegramVoice delegation passes channel=telegram_text")

    test_telegram_voice_delegation_passes_audit_db_path()
    print("  ✓ TelegramVoice delegation passes audit_db_path")

    print("\n15/15 checks PASS — next_step_proposer extraction verified.")
