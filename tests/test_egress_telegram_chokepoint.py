from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


def _pt(origin_class: str, text: str = "hello"):
    from core.egress.provenance import ProvenanceSpan, ProvenancedText

    return ProvenancedText.from_spans(
        [
            ProvenanceSpan(
                text=text,
                origin_class=origin_class,
                source_ref=f"test:{origin_class}",
                redaction_allowed=origin_class
                in {"memory", "lived_store", "owner_message_context", "third_party_private_context"},
            )
        ]
    )


def _decision(call_class: str, origin_class: str, text: str = "hello"):
    from core.egress.gate import EgressRequest, decide_egress

    return decide_egress(
        EgressRequest(
            call_class=call_class,
            destination="telegram:test",
            caller="test",
            request_id="telegram-test",
            segments=_pt(origin_class, text).to_egress_segments(),
        )
    )


class FakeTelegramBot:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    async def send_message(self, **kwargs):
        self.calls.append(("send_message", kwargs))
        return type("Msg", (), {"message_id": 123})()

    async def send_photo(self, **kwargs):
        self.calls.append(("send_photo", kwargs))
        return type("Msg", (), {"message_id": 456})()


class TelegramVocabularyAndPolicyTests(unittest.TestCase):
    def test_public_transport_origin_is_closed_vocabulary_intentional_outbound(self):
        from core.egress import gate

        origin = "maez_authored_public_third_party_transport"
        self.assertIn(origin, gate.INTENTIONAL_OUTBOUND)
        self.assertIn(origin, gate.KNOWN_ORIGINS)
        self.assertNotIn(origin, gate.NON_PRIVATE)
        self.assertNotIn(origin, gate.MINIMIZABLE_PRIVATE_CONTEXT)
        self.assertNotIn(origin, gate.UNTRUSTED_EXTERNAL_OUTPUT)
        self.assertNotIn(origin, gate.RESERVED_DENIED_RAW)

    def test_public_transport_factory_preserves_public_telegram_etiology(self):
        from core.egress.provenance import ProvenancedText

        text = ProvenancedText.maez_authored_public_third_party_transport(
            "public bot reply",
            source_ref="telegram_public:reply",
        )

        self.assertEqual(
            text.spans[0].origin_class,
            "maez_authored_public_third_party_transport",
        )
        self.assertFalse(text.spans[0].redaction_allowed)

    def test_owner_telegram_policy_allows_bond_surface_context(self):
        for origin in (
            "maez_authored_owner_third_party_transport",
            "memory",
            "lived_store",
            "owner_message_context",
            "public_fact",
            "system_bounded_query",
        ):
            with self.subTest(origin=origin):
                decision = _decision("owner_third_party_transport_send", origin)
                self.assertEqual(decision.decision, "allow")

    def test_owner_telegram_policy_minimizes_third_party_private_context(self):
        decision = _decision(
            "owner_third_party_transport_send",
            "third_party_private_context",
            "third party phone 555-555-5555",
        )

        self.assertEqual(decision.decision, "redact")
        self.assertIn("minimized_private_context", decision.reason_codes)
        self.assertNotIn("555-555-5555", decision.sanitized_text())

    def test_owner_telegram_policy_blocks_reserved_raw_and_public_mismatch(self):
        reserved = _decision("owner_third_party_transport_send", "soul", "raw soul")
        self.assertEqual(reserved.decision, "block")
        self.assertIn("reserved_denied_raw", reserved.reason_codes)

        mismatch = _decision(
            "owner_third_party_transport_send",
            "maez_authored_public_third_party_transport",
        )
        self.assertEqual(mismatch.decision, "block")
        self.assertIn("audience_origin_mismatch", mismatch.reason_codes)

    def test_public_telegram_policy_blocks_owner_context_by_default(self):
        allowed = _decision(
            "public_third_party_transport_send",
            "maez_authored_public_third_party_transport",
        )
        self.assertEqual(allowed.decision, "allow")

        for origin in (
            "maez_authored_owner_third_party_transport",
            "memory",
            "lived_store",
            "owner_message_context",
            "third_party_private_context",
        ):
            with self.subTest(origin=origin):
                decision = _decision("public_third_party_transport_send", origin)
                self.assertEqual(decision.decision, "block")
                self.assertIn("public_recipient_owner_context_blocked", decision.reason_codes)


class TelegramChokepointBehaviorTests(unittest.TestCase):
    def test_chokepoint_sends_safe_owner_message_and_logs_non_reconstructively(self):
        from core.egress.telegram_egress import (
            TelegramEgressEnvelope,
            send_telegram_async,
        )

        bot = FakeTelegramBot()
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "telegram_egress.jsonl"
            with mock.patch.dict(
                os.environ,
                {
                    "MAEZ_TELEGRAM_EGRESS_LOG": str(log_path),
                    "MAEZ_EGRESS_TELEMETRY_KEY": "telegram-test-key",
                },
                clear=False,
            ):
                result = asyncio.run(
                    send_telegram_async(
                        envelope=TelegramEgressEnvelope(
                            bot_route="owner_private",
                            audience_class="bonded_owner",
                            chat_id="123456",
                            message_kind="text",
                            content=_pt("maez_authored_owner_third_party_transport", "owner hello"),
                            caption=None,
                            interactive_markup=None,
                            media_ref=None,
                            reply_to=None,
                            source_ref="test:owner",
                            request_id="req-owner",
                            metadata={},
                        ),
                        bot=bot,
                    )
                )

            self.assertTrue(result.sent)
            self.assertEqual(result.decision.decision, "allow")
            self.assertEqual(bot.calls[0][0], "send_message")
            self.assertEqual(bot.calls[0][1]["text"], "owner hello")
            row = json.loads(log_path.read_text().splitlines()[0])
            rendered = repr(row)
            self.assertNotIn("owner hello", rendered)
            self.assertNotIn("123456", rendered)
            self.assertTrue(row["chat_id_digest"].startswith("hmac-sha256:"))

    def test_chokepoint_blocks_reserved_raw_without_maez_visible_side_effect(self):
        from core.egress.telegram_egress import (
            TelegramEgressEnvelope,
            send_telegram_async,
        )

        bot = FakeTelegramBot()
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "telegram_egress.jsonl"
            with mock.patch.dict(
                os.environ,
                {
                    "MAEZ_TELEGRAM_EGRESS_LOG": str(log_path),
                    "MAEZ_EGRESS_TELEMETRY_KEY": "telegram-test-key",
                },
                clear=False,
            ):
                result = asyncio.run(
                    send_telegram_async(
                        envelope=TelegramEgressEnvelope(
                            bot_route="owner_private",
                            audience_class="bonded_owner",
                            chat_id="123456",
                            message_kind="text",
                            content=_pt("soul", "raw soul canary"),
                            caption=None,
                            interactive_markup=None,
                            media_ref=None,
                            reply_to=None,
                            source_ref="test:soul",
                            request_id="req-block",
                            metadata={},
                        ),
                        bot=bot,
                    )
                )

            self.assertFalse(result.sent)
            self.assertEqual(bot.calls, [])
            self.assertEqual(result.maez_visible_diagnostic, None)
            row = json.loads(log_path.read_text().splitlines()[0])
            rendered = repr(row)
            self.assertIn("reserved_denied_raw", row["reason_codes"])
            self.assertNotIn("raw soul canary", rendered)
            self.assertNotIn("123456", rendered)

    def test_runtime_refuses_raw_string_without_legacy_shim(self):
        from core.egress.telegram_egress import send_telegram_async

        bot = FakeTelegramBot()
        result = asyncio.run(send_telegram_async(envelope="raw text", bot=bot))

        self.assertFalse(result.sent)
        self.assertIn("raw_payload", result.reason_codes)
        self.assertEqual(bot.calls, [])

    def test_legacy_text_envelope_is_unclassified_and_shadow_only(self):
        from core.egress.telegram_egress import legacy_text_envelope

        envelope = legacy_text_envelope(
            bot_route="owner_private",
            audience_class="bonded_owner",
            chat_id="123",
            text="legacy owner text",
            source_ref="telegram_adapter:legacy_text",
            request_id="legacy-1",
        )

        self.assertEqual(envelope.content.spans[0].origin_class, "unclassified")
        self.assertTrue(envelope.allow_legacy_shadow_send)

    def test_legacy_shadow_send_does_not_bypass_reserved_raw_blocks(self):
        from core.egress.provenance import ProvenancedText
        from core.egress.telegram_egress import (
            TelegramEgressEnvelope,
            send_telegram_async,
        )

        bot = FakeTelegramBot()
        envelope = TelegramEgressEnvelope(
            bot_route="owner_private",
            audience_class="bonded_owner",
            chat_id="123",
            message_kind="text",
            content=ProvenancedText.reserved_raw(
                "raw soul canary",
                origin_class="soul",
                source_ref="test:soul",
            ),
            caption=None,
            interactive_markup=None,
            media_ref=None,
            reply_to=None,
            source_ref="test:soul",
            request_id="reserved-shadow",
            metadata={},
            allow_legacy_shadow_send=True,
        )

        result = asyncio.run(send_telegram_async(envelope=envelope, bot=bot))

        self.assertFalse(result.sent)
        self.assertEqual(bot.calls, [])
        self.assertIn("reserved_denied_raw", result.reason_codes)

    def test_method_helper_returns_structured_block_without_raw_call(self):
        from core.egress.provenance import ProvenancedText
        from core.egress.telegram_egress import (
            TelegramEgressEnvelope,
            TelegramEgressResult,
            call_telegram_method_async,
        )

        bot = FakeTelegramBot()
        envelope = TelegramEgressEnvelope(
            bot_route="owner_private",
            audience_class="bonded_owner",
            chat_id="123",
            message_kind="text",
            content=ProvenancedText.reserved_raw(
                "raw soul canary",
                origin_class="soul",
                source_ref="test:soul",
            ),
            caption=None,
            interactive_markup=None,
            media_ref=None,
            reply_to=None,
            source_ref="test:soul",
            request_id="reserved-method",
            metadata={},
        )

        result = asyncio.run(
            call_telegram_method_async(
                envelope=envelope,
                target=bot,
                method_name="send_message",
                kwargs={"chat_id": 123, "text": "raw soul canary"},
            )
        )

        self.assertIsInstance(result, TelegramEgressResult)
        self.assertFalse(result.sent)
        self.assertEqual(bot.calls, [])

    def test_method_helper_records_actual_text_caption_and_interactive_markup(self):
        from core.egress.telegram_egress import (
            TelegramInteractiveMarkup,
            call_telegram_method_async,
            legacy_text_envelope,
            with_interactive_markup,
        )

        bot = FakeTelegramBot()
        envelope = with_interactive_markup(
            legacy_text_envelope(
                bot_route="owner_private",
                audience_class="bonded_owner",
                chat_id="123",
                text="",
                source_ref="test:method",
                message_kind="photo",
            ),
            TelegramInteractiveMarkup(
                labels=("Allow Once", "Deny"),
                callback_data_classes=("ea:once", "ea:deny"),
                button_count=2,
            ),
        )
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "telegram_egress.jsonl"
            with mock.patch.dict(
                os.environ,
                {
                    "MAEZ_TELEGRAM_EGRESS_LOG": str(log_path),
                    "MAEZ_EGRESS_TELEMETRY_KEY": "telegram-test-key",
                },
                clear=False,
            ):
                result = asyncio.run(
                    call_telegram_method_async(
                        envelope=envelope,
                        target=bot,
                        method_name="send_photo",
                        kwargs={
                            "chat_id": 123,
                            "photo": "https://example.test/image.png",
                            "caption": "caption canary",
                            "reply_markup": object(),
                        },
                    )
                )

            row = json.loads(log_path.read_text().splitlines()[0])

        self.assertEqual(getattr(result, "message_id"), 456)
        self.assertEqual(row["char_count"], len("caption canary"))
        self.assertEqual(row["interactive_markup"]["button_count"], 2)
        self.assertTrue(
            row["interactive_markup"]["label_digest"].startswith("hmac-sha256:")
        )
        rendered = repr(row)
        self.assertNotIn("caption canary", rendered)
        self.assertNotIn("Allow Once", rendered)

    def test_method_helper_preserves_precise_public_reply_provenance(self):
        from core.egress.telegram_egress import (
            call_telegram_method_async,
            public_text_envelope,
        )

        class PublicMessage:
            def __init__(self):
                self.calls: list[dict] = []

            async def reply_text(self, **kwargs):
                self.calls.append(kwargs)
                return type("Msg", (), {"message_id": 789})()

        target = PublicMessage()
        envelope = public_text_envelope(
            chat_id="456",
            text="public safe reply",
            source_ref="telegram_public:reply_text",
            request_id="public-method",
        )

        result = asyncio.run(
            call_telegram_method_async(
                envelope=envelope,
                target=target,
                method_name="reply_text",
                kwargs={"text": "public safe reply"},
            )
        )

        self.assertEqual(getattr(result, "message_id"), 789)
        self.assertEqual(target.calls, [{"text": "public safe reply"}])

    def test_method_helper_blocks_precise_provenance_payload_mismatch(self):
        from core.egress.telegram_egress import (
            TelegramEgressResult,
            call_telegram_method_async,
            public_text_envelope,
        )

        class PublicMessage:
            def __init__(self):
                self.calls: list[dict] = []

            async def reply_text(self, **kwargs):
                self.calls.append(kwargs)
                return type("Msg", (), {"message_id": 789})()

        target = PublicMessage()
        envelope = public_text_envelope(
            chat_id="456",
            text="public safe placeholder",
            source_ref="telegram_public:reply_text",
            request_id="public-method-mismatch",
        )

        result = asyncio.run(
            call_telegram_method_async(
                envelope=envelope,
                target=target,
                method_name="reply_text",
                kwargs={"text": "owner private payload"},
            )
        )

        self.assertIsInstance(result, TelegramEgressResult)
        self.assertFalse(result.sent)
        self.assertEqual(target.calls, [])

    def test_legacy_shadow_send_requires_diagnostic_write(self):
        from core.egress.telegram_egress import (
            call_telegram_method_async,
            legacy_text_envelope,
        )

        bot = FakeTelegramBot()
        envelope = legacy_text_envelope(
            bot_route="owner_private",
            audience_class="bonded_owner",
            chat_id="123",
            text="legacy owner text",
            source_ref="test:legacy",
            message_kind="text",
        )
        with mock.patch(
            "core.egress.telegram_egress._diagnostic_path",
            return_value=Path("/dev/null/telegram-egress.jsonl"),
        ):
            with self.assertRaises(Exception):
                asyncio.run(
                    call_telegram_method_async(
                        envelope=envelope,
                        target=bot,
                        method_name="send_message",
                        kwargs={"chat_id": 123, "text": "legacy owner text"},
                    )
                )

        self.assertEqual(bot.calls, [])

    def test_telegram_adapter_extracts_inline_keyboard_markup_for_envelope(self):
        from skills.surface.telegram_adapter import TelegramAdapter
        from skills.surface.platform_config import PlatformConfig

        adapter = TelegramAdapter(PlatformConfig())

        class Button:
            def __init__(self, text: str, callback_data: str):
                self.text = text
                self.callback_data = callback_data

        class Markup:
            inline_keyboard = [
                [Button("Allow Once", "ea:once:1"), Button("Deny", "ea:deny:1")],
                [Button("Cancel", "mx")],
            ]

        markup = adapter._telegram_interactive_markup(Markup())

        self.assertEqual(markup.button_count, 3)
        self.assertEqual(markup.labels, ("Allow Once", "Deny", "Cancel"))
        self.assertEqual(markup.callback_data_classes, ("ea", "ea", "mx"))

    def test_telegram_adapter_helper_raises_on_blocked_egress_result(self):
        from core.egress.provenance import ProvenancedText
        from core.egress.telegram_egress import TelegramEgressEnvelope
        from skills.surface.platform_config import PlatformConfig
        from skills.surface.telegram_adapter import TelegramAdapter

        adapter = TelegramAdapter(PlatformConfig())
        bot = FakeTelegramBot()
        adapter._bot = bot

        def blocked_envelope(**_kwargs):
            return TelegramEgressEnvelope(
                bot_route="owner_private",
                audience_class="bonded_owner",
                chat_id="123",
                message_kind="text",
                content=ProvenancedText.reserved_raw(
                    "raw soul canary",
                    origin_class="soul",
                    source_ref="test:adapter-block",
                ),
                caption=None,
                interactive_markup=None,
                media_ref=None,
                reply_to=None,
                source_ref="test:adapter-block",
                request_id="adapter-block",
                metadata={},
            )

        adapter._telegram_egress_envelope = blocked_envelope

        with self.assertRaisesRegex(RuntimeError, "telegram egress blocked"):
            asyncio.run(
                adapter._egress_call(
                    "send_message",
                    message_kind="text",
                    source_ref="test:adapter-block",
                    chat_id=123,
                    text="raw soul canary",
                )
            )

        self.assertEqual(bot.calls, [])


if __name__ == "__main__":
    unittest.main()
