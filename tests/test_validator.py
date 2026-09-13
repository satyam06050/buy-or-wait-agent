from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal

from code.ingestion import FinancialEvent, PaymentOption, Request
from code.validator import OutputRow, ValidationError, validate_output_row


class ValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.request = Request(
            request_id="request_test", user_id="user_test", request_date=date(2026, 1, 1),
            request_type="purchase", requested_amount=Decimal("100"),
            desired_completion_date=date(2026, 1, 10), allows_partial_payment=True,
            request_text="test",
        )
        self.flexible = FinancialEvent(
            event_id="event_flexible", user_id="user_test", event_type="subscription",
            description="streaming", category="subscription", direction="debit",
            amount=Decimal("20"), currency="USD", event_date=date(2025, 12, 1),
            settlement_date=date(2025, 12, 1), status="settled", linked_event_id=None,
            flexibility="stoppable", minimum_allowed_amount=Decimal("5"),
        )
        self.option = PaymentOption(
            payment_option_id="option_1", request_id="request_test", payment_method="installments",
            payment_amount=Decimal("55"), number_of_payments=2,
            first_payment_date=date(2026, 1, 2), payment_frequency_days=7,
            financing_fee=Decimal("10"), total_payable_amount=Decimal("110"),
        )

    def row(self, **changes) -> OutputRow:
        values = dict(
            request_id="request_test", amount_safe_to_pay=Decimal("40"),
            affordability_status="affordable_with_plan", recommended_payment_method="partial_payment",
            payment_plan="2026-01-01:40|2026-01-08:60", earliest_date_for_full_payment=date(2026, 1, 8),
            spending_changes_needed="none", decision_explanation="Pay part now and complete the request safely.",
        )
        values.update(changes)
        return OutputRow(**values)

    def test_valid_partial_payment(self) -> None:
        validate_output_row(self.row(), self.request, [], {self.flexible.event_id: self.flexible})

    def test_valid_installment_schedule_must_match_source_option(self) -> None:
        row = self.row(
            amount_safe_to_pay=Decimal("40"),
            recommended_payment_method="installments",
            payment_plan="2026-01-02:55|2026-01-09:55",
            earliest_date_for_full_payment=date(2026, 1, 1),
        )
        validate_output_row(row, self.request, [self.option], {self.flexible.event_id: self.flexible})

    def test_valid_full_payment_and_affordable_now(self) -> None:
        row = self.row(
            amount_safe_to_pay=Decimal("100"), affordability_status="affordable_now",
            recommended_payment_method="full_payment", payment_plan="2026-01-01:100",
            earliest_date_for_full_payment=date(2026, 1, 1),
        )
        validate_output_row(row, self.request, [], {self.flexible.event_id: self.flexible})

    def test_rejects_bad_partial_sum_and_out_of_order_dates(self) -> None:
        with self.assertRaises(ValidationError):
            validate_output_row(
                self.row(payment_plan="2026-01-08:60|2026-01-01:40"),
                self.request, [], {self.flexible.event_id: self.flexible},
            )

    def test_rejects_installment_that_does_not_match_source(self) -> None:
        row = self.row(
            recommended_payment_method="installments",
            payment_plan="2026-01-02:50|2026-01-09:50",
            earliest_date_for_full_payment=date(2026, 1, 1),
        )
        with self.assertRaises(ValidationError):
            validate_output_row(row, self.request, [self.option], {self.flexible.event_id: self.flexible})

    def test_rejects_nonflexible_or_conflicting_spending_changes(self) -> None:
        row = self.row(spending_changes_needed="stop:event_flexible|reduce_to:event_flexible:5")
        with self.assertRaises(ValidationError):
            validate_output_row(row, self.request, [], {self.flexible.event_id: self.flexible})


if __name__ == "__main__":
    unittest.main()
