from __future__ import annotations

import unittest
from datetime import date, timedelta
from decimal import Decimal

from code.forecast import blank_amount_events, build_user_forecast
from code.ingestion import load_dataset


class ForecastTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = load_dataset("dataset")

    def test_builds_inclusive_90_day_curve_from_current_balance(self) -> None:
        result = build_user_forecast(self.data, "user_01", date(2024, 3, 3))
        self.assertEqual(result.window_end, date(2024, 6, 1))
        self.assertEqual(len(result.baseline_curve), 91)
        self.assertEqual(result.baseline_curve[date(2024, 3, 3)], Decimal("58481.1"))

    def test_known_future_debit_and_confirmed_salary_are_included(self) -> None:
        result = build_user_forecast(self.data, "user_01", date(2024, 3, 3))
        ids = {item.original_event_id for item in result.included_items}
        self.assertIn("event_102", ids)  # pending debit is reserved
        self.assertIn("event_103", ids)  # scheduled confirmed salary
        self.assertTrue(any(item.source == "recurring_monthly" for item in result.included_items))

    def test_blank_amounts_are_reported_and_never_included(self) -> None:
        all_blank = blank_amount_events(self.data)
        self.assertEqual(len(all_blank), 16)
        result = build_user_forecast(self.data, "user_03", date(2019, 9, 3))
        self.assertEqual([event.event_id for event in result.blank_amount_events], ["event_253"])
        self.assertNotIn("event_253", {item.original_event_id for item in result.included_items})
        self.assertIn(
            ("event_253", "blank_amount_pending_stage_5"),
            {(event.event_id, event.reason) for event in result.excluded_events},
        )
        self.assertFalse(any("salary" in item.source for item in result.included_items))

    def test_pending_credits_failed_cancelled_and_unrealized_values_are_excluded(self) -> None:
        user20 = build_user_forecast(self.data, "user_20", date(2026, 2, 7))
        included20 = {item.original_event_id for item in user20.included_items}
        self.assertIn("event_1787", included20)  # pending debit is reserved
        self.assertNotIn("event_1785", included20)  # pending refund is not cash
        self.assertIn(("event_1785", "pending_credit"), {(e.event_id, e.reason) for e in user20.excluded_events})

        user21 = build_user_forecast(self.data, "user_21", date(2026, 4, 3))
        included21 = {item.original_event_id for item in user21.included_items}
        self.assertNotIn("event_1856", included21)  # unrealized portfolio value
        self.assertIn(("event_1856", "unrealized_non_cash"), {(e.event_id, e.reason) for e in user21.excluded_events})

    def test_foreign_confirmed_salary_uses_exact_dated_rate(self) -> None:
        result = build_user_forecast(self.data, "user_25", date(2024, 3, 6))
        salary = next(item for item in result.included_items if item.original_event_id == "event_2288")
        self.assertEqual(salary.amount, Decimal("28499994.00"))
        self.assertEqual(salary.direction, "credit")


if __name__ == "__main__":
    unittest.main()
