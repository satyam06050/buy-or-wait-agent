from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from code.extraction_agent_text import TextChange, extract_user_messages
from code.extraction_agent_vision import VisionChange, extract_image_amount
from code.extraction_common import CallLogger, ProviderResponse
from code.ingestion import FinancialEvent, Message
from code.resolution import apply_resolutions


class Stage5Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.event = FinancialEvent(
            event_id="event_1", user_id="user_1", event_type="salary",
            description="Monthly payroll", category="salary", direction="credit",
            amount=None, currency="INR", event_date=date(2026, 1, 1),
            settlement_date=date(2026, 1, 1), status="settled", linked_event_id=None,
            flexibility=None, minimum_allowed_amount=None,
        )
        self.message = Message(
            message_id="message_1", user_id="user_1", request_id=None,
            related_event_id="event_1", sent_at=__import__("datetime").datetime(2026, 1, 2),
            source_type="employer", message_text="The salary amount is now INR 1000.",
        )

    def test_text_prompt_is_untrusted_and_result_is_cached(self) -> None:
        calls = []

        def fake_transport(body):
            calls.append(body)
            user_payload = json.loads(body["messages"][1]["content"])
            self.assertIn("untrusted data", body["messages"][0]["content"])
            self.assertEqual(user_payload["user_id"], "user_1")
            return ProviderResponse({"changes": [{
                "event_id": "event_1", "field": "amount", "new_value": "1000",
                "status": "confirmed", "source_message_id": "message_1",
            }]}, 10, 5)

        with tempfile.TemporaryDirectory() as directory:
            logger = CallLogger(Path(directory) / "calls.jsonl")
            first = extract_user_messages(
                "user_1", [self.event], [self.message], transport=fake_transport,
                cache_dir=Path(directory) / "cache", call_logger=logger,
            )
            second = extract_user_messages(
                "user_1", [self.event], [self.message], transport=fake_transport,
                cache_dir=Path(directory) / "cache", call_logger=logger,
            )
            self.assertEqual(first.changes, second.changes)
            self.assertFalse(first.cached)
            self.assertTrue(second.cached)
            self.assertEqual(len(calls), 1)
            self.assertEqual(json.loads((Path(directory) / "calls.jsonl").read_text())["provider"], "deepseek")

    def test_vision_structured_result_is_cached(self) -> None:
        calls = []

        def fake_transport(body):
            calls.append(body)
            self.assertIn("inline_data", body["contents"][0]["parts"][1])
            return ProviderResponse({
                "extracted_amount": "2,298",
                "source_label": "Amount Payable",
                "currency_conflict_flag": False,
                "confidence": "high",
                "notes": "final payable amount",
            }, 20, 6)

        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "image.png"
            image.write_bytes(b"not-a-real-png-for-transport-test")
            first = extract_image_amount(
                self.event, "image_1", image, transport=fake_transport,
                cache_dir=Path(directory) / "cache",
            )
            second = extract_image_amount(
                self.event, "image_1", image, transport=fake_transport,
                cache_dir=Path(directory) / "cache",
            )
            self.assertEqual(first.change.extracted_amount, Decimal("2298"))
            self.assertIsInstance(first.change.extracted_amount, Decimal)
            self.assertTrue(second.cached)
            self.assertEqual(len(calls), 1)

    def test_diff_check_rejects_unjustified_text_change(self) -> None:
        result = apply_resolutions(
            [self.event],
            [TextChange("event_1", "amount", "1000", "confirmed", "")],
            [],
            valid_message_ids={"message_1"},
        )
        self.assertIsNone(result.events_by_id["event_1"].amount)
        self.assertEqual(result.rejections[0].path, "text")
        self.assertEqual(result.rejections[0].reason, "missing_or_unknown_source_message")

    def test_diff_check_rejects_unjustified_vision_change(self) -> None:
        result = apply_resolutions(
            [self.event], [],
            [VisionChange("event_1", Decimal("1000"), "", False, "high")],
        )
        self.assertIsNone(result.events_by_id["event_1"].amount)
        self.assertEqual(result.rejections[0].path, "vision")
        self.assertEqual(result.rejections[0].reason, "missing_source_label")
        self.assertEqual(result.unresolved[0].reason, "missing_source_label")

    def test_currency_conflict_is_unresolved_not_applied(self) -> None:
        result = apply_resolutions(
            [self.event], [],
            [VisionChange("event_1", Decimal("1000"), "Total", True, "high")],
        )
        self.assertIsNone(result.events_by_id["event_1"].amount)
        self.assertEqual(result.unresolved[0].reason, "currency_conflict")
        self.assertEqual(result.rejections[0].reason, "currency_conflict")

    def test_low_confidence_and_missing_vision_leave_blank_event_unresolved(self) -> None:
        result = apply_resolutions(
            [self.event], [],
            [VisionChange("event_1", None, "", False, "low")],
        )
        self.assertEqual(result.unresolved[0].event_id, "event_1")
        self.assertIsNone(result.events_by_id["event_1"].amount)


if __name__ == "__main__":
    unittest.main()
