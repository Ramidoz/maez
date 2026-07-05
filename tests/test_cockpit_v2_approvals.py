import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock


def _paths(root: Path):
    from core.cockpit.approvals import CockpitApprovalPaths

    return CockpitApprovalPaths(
        cards_db=root / "memory" / "pending_cards.db",
        receipt_log=root / "logs" / "cockpit_approval_receipts.jsonl",
    )


def _seed_card(cards_db: Path, *, request_id: str, action: str, status: str = "open") -> None:
    cards_db.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(cards_db)) as con, con:
        con.execute(
            """
            CREATE TABLE pending_cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL UNIQUE,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                status TEXT NOT NULL,
                action TEXT NOT NULL,
                params_json TEXT NOT NULL,
                reason TEXT,
                plain_english TEXT,
                proposed_action_summary TEXT,
                completed_action_summary TEXT,
                audit_decision TEXT,
                audit_confidence REAL,
                audit_reasoning TEXT,
                audit_concerns_json TEXT,
                audit_mitigations_json TEXT,
                audit_summary TEXT,
                audit_answers_json TEXT,
                audit_request_id TEXT,
                intent_category TEXT,
                lane TEXT,
                state_hash TEXT NOT NULL,
                state_fields_json TEXT,
                channel TEXT NOT NULL,
                channel_message_id TEXT,
                chat_id TEXT,
                user_id TEXT,
                remind_at REAL,
                defer_reason TEXT,
                defer_count INTEGER NOT NULL DEFAULT 0,
                resolved_at REAL,
                resolved_by_user_id TEXT,
                resolved_via TEXT,
                resolution_notes TEXT,
                executed_at REAL,
                execution_success INTEGER,
                execution_output TEXT,
                execution_error TEXT
            )
            """
        )
        con.execute(
            """
            INSERT INTO pending_cards (
                request_id, created_at, updated_at, status, action, params_json,
                reason, plain_english, proposed_action_summary, audit_confidence,
                audit_concerns_json, audit_mitigations_json, audit_answers_json,
                state_hash, channel, defer_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_id,
                1000.0,
                1000.0,
                status,
                action,
                json.dumps({"cmd": "systemctl restart maez.service"} if action == "run_shell" else {}),
                "owner approval requested",
                "Restart maez.service",
                "Restart maez.service",
                0.0,
                "[]",
                "[]",
                "{}",
                "empty",
                "telegram_text",
                0,
            ),
        )


class CockpitV2ApprovalsTests(unittest.TestCase):
    def test_pending_list_reads_existing_store_without_creating_it(self):
        from core.cockpit.approvals import build_approvals_room

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            room = build_approvals_room(_paths(root))
            created = sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))

        self.assertEqual(created, [])
        self.assertEqual(room["status"], "no_data")
        self.assertEqual(room["pending_count"], 0)

    def test_pending_list_reports_real_pending_cards_and_tiers(self):
        from core.cockpit.approvals import build_approvals_room

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            paths = _paths(root)
            _seed_card(paths.cards_db, request_id="card-t2", action="run_shell")

            room = build_approvals_room(paths)

        self.assertEqual(room["status"], "ok")
        self.assertEqual(room["pending_count"], 1)
        self.assertEqual(room["pending"][0]["request_id"], "card-t2")
        self.assertEqual(room["pending"][0]["decision_tier"], "T2")
        self.assertEqual(room["pending"][0]["channel"], "existing_pending_cards")

    def test_t2_approve_requires_typed_confirmation_before_existing_channel(self):
        from core.cockpit.approvals import apply_approval_decision

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            paths = _paths(root)
            _seed_card(paths.cards_db, request_id="card-t2", action="run_shell")

            result = apply_approval_decision(
                "card-t2",
                "approve",
                paths=paths,
                owner_authenticated=True,
                confirm_click_token="confirm",
                existing_approve_channel=lambda _request_id, _payload: {"ok": True},
            )

            self.assertFalse(paths.receipt_log.exists())

        self.assertEqual(result["status"], "refused")
        self.assertEqual(result["reason"], "typed_confirmation_required")
        self.assertEqual(result["required_confirmation"], "APPROVE card-t2")

    def test_approve_routes_through_existing_channel_and_writes_receipt(self):
        from core.cockpit.approvals import apply_approval_decision

        calls = []

        def existing_channel(request_id, payload):
            calls.append((request_id, payload))
            return {"ok": True, "status": "executed"}

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            paths = _paths(root)
            _seed_card(paths.cards_db, request_id="card-t2", action="run_shell")

            result = apply_approval_decision(
                "card-t2",
                "approve",
                paths=paths,
                owner_authenticated=True,
                confirm_click_token="confirm",
                typed_confirmation="APPROVE card-t2",
                existing_approve_channel=existing_channel,
            )
            receipt = json.loads(paths.receipt_log.read_text(encoding="utf-8"))

        self.assertEqual(calls, [("card-t2", {"edited_params": None})])
        self.assertEqual(result["status"], "applied")
        self.assertEqual(result["decision"], "approve")
        self.assertEqual(receipt["request_id"], "card-t2")
        self.assertEqual(receipt["decision"], "approve")
        self.assertEqual(receipt["channel"], "existing_approval_channel")

    def test_reject_uses_existing_pending_card_channel_and_writes_receipt(self):
        from core.cockpit.approvals import apply_approval_decision

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            paths = _paths(root)
            _seed_card(paths.cards_db, request_id="card-t2", action="run_shell")

            result = apply_approval_decision(
                "card-t2",
                "reject",
                paths=paths,
                owner_authenticated=True,
                confirm_click_token="confirm",
            )
            with closing(sqlite3.connect(paths.cards_db)) as con:
                status = con.execute(
                    "SELECT status FROM pending_cards WHERE request_id = ?",
                    ("card-t2",),
                ).fetchone()[0]
            receipt = json.loads(paths.receipt_log.read_text(encoding="utf-8"))

        self.assertEqual(result["status"], "applied")
        self.assertEqual(result["decision"], "reject")
        self.assertEqual(status, "denied")
        self.assertEqual(receipt["decision"], "reject")
        self.assertEqual(receipt["channel"], "existing_pending_cards")

    def test_v2_route_uses_existing_approve_proxy_and_no_auto_approval(self):
        os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test")
        os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")
        import skills.web_interface as wi

        wi.app.config["TESTING"] = True
        captured = {}

        def fake_existing_channel(request_id, payload):
            captured["request_id"] = request_id
            captured["payload"] = payload
            return {"ok": True, "status": "executed"}

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            paths = _paths(root)
            _seed_card(paths.cards_db, request_id="card-t2", action="run_shell")
            with mock.patch.dict(os.environ, {"MAEZ_COCKPIT_V2": "1"}, clear=False), (
                mock.patch.object(wi, "_owner_private_auth_ok", return_value=True)
            ), mock.patch.object(wi, "_cockpit_approval_paths", return_value=paths), (
                mock.patch.object(wi, "_cockpit_existing_approve_channel", side_effect=fake_existing_channel)
            ):
                missing_confirm = wi.app.test_client().post(
                    "/api/v2/cockpit/approvals/card-t2",
                    json={"decision": "approve", "confirm_click_token": "confirm"},
                )
                ok = wi.app.test_client().post(
                    "/api/v2/cockpit/approvals/card-t2",
                    json={
                        "decision": "approve",
                        "confirm_click_token": "confirm",
                        "typed_confirmation": "APPROVE card-t2",
                    },
                )

        self.assertEqual(missing_confirm.status_code, 400)
        self.assertEqual(missing_confirm.get_json()["reason"], "typed_confirmation_required")
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(captured["request_id"], "card-t2")
        self.assertEqual(captured["payload"], {"edited_params": None})

    def test_v2_ui_uses_approvals_room_endpoint(self):
        sim = Path("web/cockpit/v2/sim.jsx").read_text(encoding="utf-8")
        ui = Path("web/cockpit/v2/terminal-ui.jsx").read_text(encoding="utf-8")

        self.assertIn("/api/v2/cockpit/approvals", sim)
        self.assertIn("approvalsRoom", sim)
        self.assertIn("decision_tier", ui)
        self.assertIn("confirmApproval", ui)


if __name__ == "__main__":
    unittest.main()
