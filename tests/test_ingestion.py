from __future__ import annotations

import unittest
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from code.ingestion import load_dataset


DATASET = Path(__file__).resolve().parents[1] / "dataset"


class IngestionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = load_dataset(DATASET)

    def test_loads_every_participant_csv(self) -> None:
        self.assertEqual(len(self.data.profiles), 275)
        self.assertEqual(len(self.data.events), 25342)
        self.assertEqual(len(self.data.requests), 250)
        self.assertEqual(len(self.data.sample_requests), 25)
        self.assertEqual(len(self.data.payment_options), 790)
        self.assertEqual(len(self.data.messages), 215)
        self.assertEqual(len(self.data.images), 16)
        self.assertEqual(len(self.data.exchange_rates), 134)
        self.assertEqual(len(self.data.output_template), 250)

    def test_normalizes_dates_decimals_booleans_and_pipe_fields(self) -> None:
        profile = self.data.profiles_by_user["user_02"]
        self.assertEqual(profile.current_available_balance, Decimal("60383889.2"))
        self.assertEqual(profile.financial_priorities, ("education", "family_support"))
        self.assertEqual(profile.payment_methods_user_will_consider, ("partial_payment", "installments"))
        self.assertEqual(profile.max_installment_months, 7)

        sample = self.data.sample_requests_by_id["request_01"]
        self.assertEqual(sample.request_date, date(2024, 3, 3))
        self.assertTrue(sample.allows_partial_payment)
        self.assertEqual(sample.requested_amount, Decimal("25256"))

        request = self.data.requests_by_id["request_26"]
        self.assertEqual(request.request_date, date(2025, 8, 3))
        self.assertFalse(request.allows_partial_payment)

        message = self.data.messages_by_id["message_01"]
        self.assertEqual(message.sent_at, datetime(2025, 7, 29, 9, 30, tzinfo=timezone.utc))

    def test_blank_amount_is_none_not_zero(self) -> None:
        self.assertIsNone(self.data.events_by_id["event_253"].amount)
        self.assertIsNone(self.data.events_by_id["event_1442"].amount)

    def test_builds_user_request_event_message_image_and_option_indices(self) -> None:
        self.assertEqual(len(self.data.events_by_user["user_01"]), 103)
        self.assertEqual(self.data.requests_by_id["request_26"].user_id, "user_26")
        self.assertEqual(self.data.payment_options_by_request["request_01"][0].payment_option_id, "payment_option_01")
        self.assertEqual(self.data.messages_by_event["event_1785"][0].message_id, "message_14")
        self.assertEqual(self.data.images_by_event["event_1545"][0].image_id, "image_03")
        self.assertEqual(self.data.images_by_request["request_20"][0].image_id, "image_05")

    def test_loads_blank_output_template_fields_as_none(self) -> None:
        row = self.data.output_template_by_request["request_26"]
        self.assertIsNone(row.amount_safe_to_pay)
        self.assertIsNone(row.affordability_status)
        self.assertIsNone(row.earliest_date_for_full_payment)


if __name__ == "__main__":
    unittest.main()
