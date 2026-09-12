from __future__ import annotations

import unittest
from datetime import date, timedelta
from decimal import Decimal

from code.decision_engine import (
    CandidatePlan,
    InstallmentOption,
    Payment,
    SpendingChange,
    amount_safe_to_pay,
    earliest_date_for_full_payment,
    generate_candidate_plans,
    rank_and_select,
    spending_changes,
)


def d(day: int) -> date:
    return date(2026, 1, day)


class DecisionEngineTests(unittest.TestCase):
    def test_amount_safe_to_pay_uses_unmodified_curve_and_caps_request(self) -> None:
        curve = {
            d(1): Decimal("200"),
            d(2): Decimal("180"),
            d(3): Decimal("160"),
            d(4): Decimal("150"),
            d(5): Decimal("220"),
        }
        self.assertEqual(
            amount_safe_to_pay(curve, Decimal("1000"), Decimal("100")),
            Decimal("50"),
        )
        self.assertEqual(
            amount_safe_to_pay(curve, Decimal("25"), Decimal("100")),
            Decimal("25"),
        )

    def test_earliest_date_for_full_payment_uses_suffix_safety(self) -> None:
        curve = {
            d(1): Decimal("150"),
            d(2): Decimal("210"),
            d(3): Decimal("205"),
            d(4): Decimal("210"),
        }
        self.assertEqual(
            earliest_date_for_full_payment(
                curve, Decimal("100"), Decimal("100"), d(4)
            ),
            d(2),
        )
        self.assertIsNone(
            earliest_date_for_full_payment(
                {d(1): Decimal("150"), d(2): Decimal("190")},
                Decimal("100"),
                Decimal("100"),
                d(2),
            )
        )

    def test_generate_candidates_covers_now_plan_later_and_fallback(self) -> None:
        curve = {
            d(1): Decimal("150"),
            d(2): Decimal("190"),
            d(3): Decimal("230"),
            d(4): Decimal("240"),
            d(5): Decimal("240"),
        }
        option = InstallmentOption(
            payment_option_id="payment_option_01",
            payment_method="installments",
            payments=(Payment(d(2), Decimal("30")), Payment(d(4), Decimal("70"))),
            total_payable_amount=Decimal("110"),
        )
        candidates = generate_candidate_plans(
            curve,
            Decimal("100"),
            Decimal("100"),
            d(1),
            d(4),
            allows_partial_payment=True,
            accepted_payment_methods=("full_payment", "partial_payment", "installments"),
            installment_options=(option,),
        )
        self.assertIn("affordable_with_plan", {candidate.affordability_status for candidate in candidates})
        self.assertTrue(any(candidate.payment_method == "partial_payment" and candidate.safe for candidate in candidates))
        self.assertTrue(any(candidate.payment_method == "installments" and candidate.safe for candidate in candidates))

        later_candidates = generate_candidate_plans(
            curve,
            Decimal("100"),
            Decimal("100"),
            d(1),
            d(4),
            allows_partial_payment=False,
            accepted_payment_methods=("full_payment",),
        )
        wait = next(candidate for candidate in later_candidates if candidate.payment_method == "wait")
        self.assertEqual(wait.affordability_status, "affordable_later")
        self.assertTrue(wait.safe)

        fallback = generate_candidate_plans(
            curve,
            Decimal("100"),
            Decimal("100"),
            d(1),
            d(2),
            allows_partial_payment=False,
            accepted_payment_methods=("full_payment",),
        )
        self.assertEqual(fallback[-1].payment_method, "not_recommended")
        self.assertEqual(fallback[-1].affordability_status, "not_affordable")

        now = generate_candidate_plans(
            {d(1): Decimal("250"), d(2): Decimal("240")},
            Decimal("100"),
            Decimal("100"),
            d(1),
            d(2),
            allows_partial_payment=False,
            accepted_payment_methods=("full_payment",),
        )
        self.assertEqual(now[0].affordability_status, "affordable_now")
        self.assertTrue(now[0].safe)

    def test_partial_payment_is_rejected_after_completion_deadline(self) -> None:
        curve = {
            d(1): Decimal("150"),
            d(2): Decimal("190"),
            d(3): Decimal("220"),
            d(4): Decimal("230"),
        }
        candidates = generate_candidate_plans(
            curve,
            Decimal("100"),
            Decimal("100"),
            d(1),
            d(2),
            allows_partial_payment=True,
            accepted_payment_methods=("partial_payment",),
        )
        self.assertFalse(any(candidate.payment_method == "partial_payment" for candidate in candidates))
        self.assertEqual(candidates[-1].payment_method, "not_recommended")

    def test_installment_schedule_is_copied_verbatim(self) -> None:
        option = InstallmentOption(
            payment_option_id="payment_option_07",
            payment_method="installments",
            payments=(
                Payment(d(2), Decimal("40.25")),
                Payment(d(4), Decimal("40.25")),
                Payment(d(5), Decimal("40.25")),
            ),
            total_payable_amount=Decimal("130.75"),
        )
        curve = {d(1): Decimal("500"), d(2): Decimal("500"), d(3): Decimal("500"), d(4): Decimal("500"), d(5): Decimal("500")}
        candidates = generate_candidate_plans(
            curve,
            Decimal("100"),
            Decimal("100"),
            d(1),
            d(5),
            allows_partial_payment=False,
            accepted_payment_methods=("installments",),
            installment_options=(option,),
        )
        candidate = candidates[0]
        self.assertEqual(candidate.payments, option.payments)
        self.assertEqual(candidate.total_paid, option.total_payable_amount)
        self.assertEqual(candidate.payment_option_id, option.payment_option_id)

    def test_each_ranking_key_is_enforced_independently(self) -> None:
        base_payment = (Payment(d(2), Decimal("100")),)

        # 1. Complete by deadline.
        incomplete = CandidatePlan("affordable_with_plan", "full_payment", base_payment, Decimal("100"), True, False)
        complete = CandidatePlan("affordable_with_plan", "full_payment", base_payment, Decimal("100"), True, True)
        self.assertIs(rank_and_select([incomplete, complete]), complete)

        # 2. No spending changes.
        changed = CandidatePlan("affordable_with_plan", "full_payment", base_payment, Decimal("100"), True, True, ("stop:event_1",))
        unchanged = CandidatePlan("affordable_with_plan", "full_payment", base_payment, Decimal("100"), True, True)
        self.assertIs(rank_and_select([changed, unchanged]), unchanged)

        # 3. Minimize total amount paid.
        expensive = CandidatePlan("affordable_with_plan", "installments", base_payment, Decimal("101"), True, True, payment_option_id="payment_option_01")
        cheap = CandidatePlan("affordable_with_plan", "installments", base_payment, Decimal("100"), True, True, payment_option_id="payment_option_02")
        self.assertIs(rank_and_select([expensive, cheap]), cheap)

        # 4. Start earlier.
        later = CandidatePlan("affordable_with_plan", "full_payment", (Payment(d(3), Decimal("100")),), Decimal("100"), True, True)
        earlier = CandidatePlan("affordable_with_plan", "full_payment", base_payment, Decimal("100"), True, True)
        self.assertIs(rank_and_select([later, earlier]), earlier)

        # 5. Use fewer payments.
        many = CandidatePlan("affordable_with_plan", "installments", (Payment(d(2), Decimal("50")), Payment(d(3), Decimal("50"))), Decimal("100"), True, True, payment_option_id="payment_option_01")
        few = CandidatePlan("affordable_with_plan", "installments", base_payment, Decimal("100"), True, True, payment_option_id="payment_option_02")
        self.assertIs(rank_and_select([many, few]), few)

        # 6. Lowest payment_option_id.
        higher_id = CandidatePlan("affordable_with_plan", "installments", base_payment, Decimal("100"), True, True, payment_option_id="payment_option_02")
        lower_id = CandidatePlan("affordable_with_plan", "installments", base_payment, Decimal("100"), True, True, payment_option_id="payment_option_01")
        self.assertIs(rank_and_select([higher_id, lower_id]), lower_id)

    def test_rank_and_select_ignores_unsafe_candidates(self) -> None:
        unsafe = CandidatePlan("affordable_now", "full_payment", (Payment(d(1), Decimal("1")),), Decimal("1"), False, True)
        safe = CandidatePlan("affordable_later", "wait", (Payment(d(2), Decimal("1")),), Decimal("1"), True, True)
        self.assertIs(rank_and_select([unsafe, safe]), safe)

    def test_spending_changes_do_not_change_frozen_safe_amount(self) -> None:
        curve = {d(1): Decimal("150"), d(2): Decimal("150"), d(3): Decimal("150")}
        frozen = amount_safe_to_pay(curve, Decimal("100"), Decimal("100"))
        result = spending_changes(
            frozen,
            (
                SpendingChange(
                    event_id="event_flexible",
                    action="stop",
                    original_amount=Decimal("40"),
                    new_amount=Decimal("0"),
                ),
            ),
        )
        self.assertEqual(frozen, Decimal("50"))
        self.assertEqual(result.amount_safe_to_pay, frozen)
        self.assertEqual(result.amount_released, Decimal("40"))


if __name__ == "__main__":
    unittest.main()
