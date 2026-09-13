"""Standalone decision-engine primitives for synthetic balance curves.

This module intentionally has no CSV or ingestion imports. It operates on
already-normalized values supplied by callers and does not resolve messages,
images, recurrence, or currency.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, Mapping, Optional, Sequence


BalanceCurve = Mapping[date, Decimal]


@dataclass(frozen=True)
class Payment:
    """One payment in a candidate plan."""

    payment_date: date
    amount: Decimal


@dataclass(frozen=True)
class InstallmentOption:
    """An already-expanded supplied option.

    The payment dates and amounts are input data. The decision engine copies
    them verbatim and never derives a schedule from a frequency or count.
    """

    payment_option_id: str
    payment_method: str
    payments: tuple[Payment, ...]
    total_payable_amount: Decimal


@dataclass(frozen=True)
class CandidatePlan:
    """A plan that can be ranked after deterministic safety evaluation."""

    affordability_status: str
    payment_method: str
    payments: tuple[Payment, ...]
    total_paid: Decimal
    safe: bool
    completes_by_deadline: bool
    spending_changes: tuple[str, ...] = ()
    payment_option_id: Optional[str] = None

    @property
    def payment_count(self) -> int:
        return len(self.payments)

    @property
    def start_date(self) -> Optional[date]:
        if not self.payments:
            return None
        return min(payment.payment_date for payment in self.payments)


@dataclass(frozen=True)
class SpendingChange:
    """A permitted flexible-event change considered after the baseline amount."""

    event_id: str
    action: str
    original_amount: Decimal
    new_amount: Decimal
    flexible: bool = True
    permitted: bool = True


@dataclass(frozen=True)
class SpendingChangeResult:
    """Validated changes with the original safe amount frozen."""

    amount_safe_to_pay: Decimal
    changes: tuple[SpendingChange, ...]
    amount_released: Decimal


def _ordered_curve(baseline_curve: BalanceCurve) -> list[tuple[date, Decimal]]:
    if not baseline_curve:
        raise ValueError("baseline_curve must contain at least one date")
    ordered = sorted(baseline_curve.items())
    for curve_date, balance in ordered:
        if not isinstance(curve_date, date):
            raise TypeError("baseline_curve keys must be datetime.date values")
        if not isinstance(balance, Decimal):
            raise TypeError("baseline_curve balances must be Decimal values")
    return ordered


def _validate_nonnegative_amount(amount: Decimal, name: str) -> None:
    if not isinstance(amount, Decimal):
        raise TypeError(f"{name} must be a Decimal")
    if amount < 0:
        raise ValueError(f"{name} must be non-negative")


def amount_safe_to_pay(
    baseline_curve: BalanceCurve,
    requested_amount: Decimal,
    minimum_balance: Decimal,
) -> Decimal:
    """Return the safe amount from the unmodified baseline curve.

    The request is applied across the complete supplied forecast, so the
    available capacity is the lowest baseline balance minus the protected
    minimum. The result is clipped to ``[0, requested_amount]`` and is not
    affected by later spending-change analysis.
    """
    _validate_nonnegative_amount(requested_amount, "requested_amount")
    _validate_nonnegative_amount(minimum_balance, "minimum_balance")
    ordered = _ordered_curve(baseline_curve)
    capacity = min(balance for _, balance in ordered) - minimum_balance
    return max(Decimal("0"), min(requested_amount, capacity))


def earliest_date_for_full_payment(
    baseline_curve: BalanceCurve,
    requested_amount: Decimal,
    minimum_balance: Decimal,
    window_end: date,
) -> Optional[date]:
    """Return the first curve date where one full payment is safe thereafter."""
    _validate_nonnegative_amount(requested_amount, "requested_amount")
    _validate_nonnegative_amount(minimum_balance, "minimum_balance")
    if not isinstance(window_end, date):
        raise TypeError("window_end must be a datetime.date value")

    ordered = [item for item in _ordered_curve(baseline_curve) if item[0] <= window_end]
    required_balance = minimum_balance + requested_amount
    for index, (candidate_date, _) in enumerate(ordered):
        if min(balance for _, balance in ordered[index:]) >= required_balance:
            return candidate_date
    return None


def _plan_is_safe(
    baseline_curve: BalanceCurve,
    payments: Sequence[Payment],
    minimum_balance: Decimal,
) -> bool:
    """Check a payment schedule against every affected forecast point."""
    ordered = _ordered_curve(baseline_curve)
    for payment in payments:
        _validate_nonnegative_amount(payment.amount, "payment amount")
        if not isinstance(payment.payment_date, date):
            raise TypeError("payment dates must be datetime.date values")

    if any(payment.payment_date > ordered[-1][0] for payment in payments):
        return False

    for curve_date, baseline_balance in ordered:
        payments_due = sum(
            (payment.amount for payment in payments if payment.payment_date <= curve_date),
            Decimal("0"),
        )
        if baseline_balance - payments_due < minimum_balance:
            return False
    return True


def _completes_by_deadline(payments: Sequence[Payment], desired_completion_date: date) -> bool:
    return bool(payments) and max(payment.payment_date for payment in payments) <= desired_completion_date


def _accepted(method: str, accepted_payment_methods: Iterable[str]) -> bool:
    return method in set(accepted_payment_methods)


def generate_candidate_plans(
    baseline_curve: BalanceCurve,
    requested_amount: Decimal,
    minimum_balance: Decimal,
    request_date: date,
    desired_completion_date: date,
    allows_partial_payment: bool,
    accepted_payment_methods: Iterable[str],
    installment_options: Iterable[InstallmentOption] = (),
) -> list[CandidatePlan]:
    """Generate safe candidates plus the deterministic fallback candidate.

    ``installment_options`` must already contain the exact supplied payment
    schedules. This function only checks their feasibility and copies their
    payment values; it does not calculate installment dates or financing.
    """
    _validate_nonnegative_amount(requested_amount, "requested_amount")
    _validate_nonnegative_amount(minimum_balance, "minimum_balance")
    if not isinstance(request_date, date) or not isinstance(desired_completion_date, date):
        raise TypeError("request_date and desired_completion_date must be datetime.date values")

    accepted = set(accepted_payment_methods)
    safe_now = amount_safe_to_pay(baseline_curve, requested_amount, minimum_balance)
    # The payment plan is checked against the complete supplied forecast. Find
    # the first date whose suffix remains safe through the forecast horizon,
    # then separately require that date to meet the request deadline below.
    forecast_end = max(baseline_curve)
    earliest_full = earliest_date_for_full_payment(
        baseline_curve, requested_amount, minimum_balance, forecast_end
    )
    candidates: list[CandidatePlan] = []

    full_payments = (Payment(request_date, requested_amount),)
    if "full_payment" in accepted:
        candidates.append(
            CandidatePlan(
                affordability_status="affordable_now",
                payment_method="full_payment",
                payments=full_payments,
                total_paid=requested_amount,
                safe=_plan_is_safe(baseline_curve, full_payments, minimum_balance),
                completes_by_deadline=_completes_by_deadline(full_payments, desired_completion_date),
            )
        )

    if (
        allows_partial_payment
        and "partial_payment" in accepted
        and Decimal("0") < safe_now < requested_amount
        and earliest_full is not None
        and earliest_full <= desired_completion_date
    ):
        partial_payments = (
            Payment(request_date, safe_now),
            Payment(earliest_full, requested_amount - safe_now),
        )
        candidates.append(
            CandidatePlan(
                affordability_status="affordable_with_plan",
                payment_method="partial_payment",
                payments=partial_payments,
                total_paid=requested_amount,
                safe=_plan_is_safe(baseline_curve, partial_payments, minimum_balance),
                completes_by_deadline=_completes_by_deadline(partial_payments, desired_completion_date),
            )
        )

    if "installments" in accepted:
        for option in installment_options:
            if option.payment_method != "installments":
                continue
            payments = tuple(option.payments)
            candidates.append(
                CandidatePlan(
                    affordability_status="affordable_with_plan",
                    payment_method="installments",
                    payments=payments,
                    total_paid=option.total_payable_amount,
                    safe=_plan_is_safe(baseline_curve, payments, minimum_balance),
                    completes_by_deadline=_completes_by_deadline(payments, desired_completion_date),
                    payment_option_id=option.payment_option_id,
                )
            )

    if (
        "full_payment" in accepted
        and earliest_full is not None
        and earliest_full > request_date
        and earliest_full <= desired_completion_date
    ):
        wait_payments = (Payment(earliest_full, requested_amount),)
        candidates.append(
            CandidatePlan(
                affordability_status="affordable_later",
                payment_method="wait",
                payments=wait_payments,
                total_paid=requested_amount,
                safe=_plan_is_safe(baseline_curve, wait_payments, minimum_balance),
                completes_by_deadline=_completes_by_deadline(wait_payments, desired_completion_date),
            )
        )

    if not any(candidate.safe for candidate in candidates):
        candidates.append(
            CandidatePlan(
                affordability_status="not_affordable",
                payment_method="not_recommended",
                payments=(),
                total_paid=Decimal("0"),
                safe=True,
                completes_by_deadline=False,
            )
        )
    return candidates


def _option_id_sort_key(payment_option_id: Optional[str]) -> str:
    # Non-option plans are tied after explicitly identified supplied options.
    return payment_option_id if payment_option_id is not None else "~"


def _rank_key(candidate: CandidatePlan) -> tuple[object, ...]:
    """The six spec keys, in their specified order only."""
    start_date = candidate.start_date or date.max
    return (
        not candidate.completes_by_deadline,
        not (len(candidate.spending_changes) == 0),
        candidate.total_paid,
        start_date,
        candidate.payment_count,
        _option_id_sort_key(candidate.payment_option_id),
    )


def rank_and_select(candidates: Iterable[CandidatePlan]) -> CandidatePlan:
    """Select the best safe plan using exactly the six specification keys."""
    available = list(candidates)
    if not available:
        raise ValueError("at least one candidate plan is required")
    safe_candidates = [candidate for candidate in available if candidate.safe]
    if not safe_candidates:
        raise ValueError("no safe candidate plan is available")
    return min(safe_candidates, key=_rank_key)


def spending_changes(
    frozen_amount_safe_to_pay: Decimal,
    changes: Sequence[SpendingChange],
) -> SpendingChangeResult:
    """Validate optional changes without recomputing safe payment capacity.

    The returned ``amount_safe_to_pay`` is exactly the supplied frozen value.
    This function reports the release created by valid changes but deliberately
    does not feed that release back into the amount calculation.
    """
    _validate_nonnegative_amount(frozen_amount_safe_to_pay, "frozen_amount_safe_to_pay")
    if len(changes) > 3:
        raise ValueError("at most three spending changes are allowed")

    seen_event_ids: set[str] = set()
    for change in changes:
        if change.event_id in seen_event_ids:
            raise ValueError(f"duplicate spending change for event {change.event_id!r}")
        seen_event_ids.add(change.event_id)
        if not change.flexible or not change.permitted:
            raise ValueError(f"spending change is not permitted for event {change.event_id!r}")
        if change.action not in {"stop", "reduce_to"}:
            raise ValueError(f"unsupported spending change action {change.action!r}")
        if change.original_amount < 0 or change.new_amount < 0:
            raise ValueError("spending change amounts must be non-negative")
        if change.new_amount > change.original_amount:
            raise ValueError("spending changes cannot increase an event amount")
        if change.action == "stop" and change.new_amount != 0:
            raise ValueError("stop changes must have new_amount equal to zero")
        if change.action == "reduce_to" and change.new_amount >= change.original_amount:
            raise ValueError("reduce_to must reduce the original amount")

    released = sum(
        (change.original_amount - change.new_amount for change in changes),
        Decimal("0"),
    )
    return SpendingChangeResult(
        amount_safe_to_pay=frozen_amount_safe_to_pay,
        changes=tuple(changes),
        amount_released=released,
    )
