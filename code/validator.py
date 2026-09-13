"""Stage 7 output invariants for one final output row."""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Iterable, Mapping, Optional

from .ingestion import FinancialEvent, PaymentOption, Request


AFFORDABILITY_STATUSES = frozenset({
    "affordable_now", "affordable_with_plan", "affordable_later", "not_affordable",
})
PAYMENT_METHODS = frozenset({
    "full_payment", "partial_payment", "installments", "wait", "not_recommended",
})
PAYMENT_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}):([0-9]+(?:\.[0-9]+)?)$")
FLEXIBLE_CAPABILITIES = frozenset({"reducible", "stoppable", "reducible_or_stoppable"})
STOP_RE = re.compile(r"^stop:([^:|]+)$")
REDUCE_RE = re.compile(r"^reduce_to:([^:|]+):([0-9]+(?:\.[0-9]+)?)$")


@dataclass(frozen=True)
class OutputRow:
    request_id: str
    amount_safe_to_pay: Decimal
    affordability_status: str
    recommended_payment_method: str
    payment_plan: str
    earliest_date_for_full_payment: Optional[date]
    spending_changes_needed: str
    decision_explanation: str


class ValidationError(ValueError):
    """One or more output invariants failed."""


def _money(value: object, field: str) -> Decimal:
    if not isinstance(value, Decimal):
        raise ValidationError(f"{field} must be Decimal")
    if not value.is_finite() or value < 0:
        raise ValidationError(f"{field} must be finite and non-negative")
    return value


def _parse_plan(value: str) -> list[tuple[date, Decimal]]:
    if value == "none":
        return []
    if not isinstance(value, str) or not value:
        raise ValidationError("payment_plan must be none or payment entries")
    payments: list[tuple[date, Decimal]] = []
    for entry in value.split("|"):
        match = PAYMENT_RE.fullmatch(entry)
        if match is None:
            raise ValidationError(f"invalid payment_plan entry: {entry!r}")
        try:
            payment_date = date.fromisoformat(match.group(1))
            amount = Decimal(match.group(2))
        except (ValueError, InvalidOperation) as exc:
            raise ValidationError(f"invalid payment_plan value: {entry!r}") from exc
        if not amount.is_finite() or amount < 0:
            raise ValidationError("payment plan amounts must be non-negative finite decimals")
        payments.append((payment_date, amount))
    if any(later < earlier for (earlier, _), (later, _) in zip(payments, payments[1:])):
        raise ValidationError("payment_plan dates must be chronological")
    return payments


def _validate_installment_schedule(
    payments: list[tuple[date, Decimal]],
    options: Iterable[PaymentOption],
) -> None:
    total = sum((amount for _, amount in payments), Decimal("0"))
    for option in options:
        expected = []
        current = option.first_payment_date
        for index in range(option.number_of_payments):
            expected.append((current, option.payment_amount))
            if option.payment_frequency_days is not None:
                current += timedelta(days=option.payment_frequency_days)
        if payments == expected and total == option.total_payable_amount:
            return
    raise ValidationError("installment payment_plan does not match any supplied option exactly")


def _validate_spending_changes(
    value: str,
    events_by_id: Mapping[str, FinancialEvent],
) -> None:
    if value == "none":
        return
    if not isinstance(value, str) or not value:
        raise ValidationError("spending_changes_needed must be none or actions")
    actions = value.split("|")
    if len(actions) > 3:
        raise ValidationError("at most three spending changes are allowed")
    seen: set[str] = set()
    action_types: dict[str, str] = {}
    for action in actions:
        stop = STOP_RE.fullmatch(action)
        reduce_to = REDUCE_RE.fullmatch(action)
        if stop is not None:
            event_id, new_amount = stop.group(1), Decimal("0")
            action_type = "stop"
        elif reduce_to is not None:
            event_id = reduce_to.group(1)
            try:
                new_amount = Decimal(reduce_to.group(2))
            except InvalidOperation as exc:
                raise ValidationError(f"invalid reduce_to amount: {action!r}") from exc
            action_type = "reduce_to"
        else:
            raise ValidationError(f"invalid spending change: {action!r}")
        if event_id in seen:
            raise ValidationError(f"duplicate or conflicting spending change: {event_id}")
        seen.add(event_id)
        if event_id not in events_by_id:
            raise ValidationError(f"spending change references unknown event: {event_id}")
        event = events_by_id[event_id]
        if event.flexibility not in FLEXIBLE_CAPABILITIES:
            raise ValidationError(f"spending change references non-flexible event: {event_id}")
        if event.amount is None or new_amount > event.amount:
            raise ValidationError(f"spending change amount is invalid for event: {event_id}")
        action_types[event_id] = action_type
    if len(action_types) != len(seen):
        raise ValidationError("an event cannot have both stop and reduce_to actions")


def validate_output_row(
    row: OutputRow,
    request: Request,
    options: Iterable[PaymentOption],
    events_by_id: Mapping[str, FinancialEvent],
) -> None:
    """Raise ValidationError if one serialized output row violates the contract."""
    if row.request_id != request.request_id:
        raise ValidationError("row request_id does not match request")
    safe_amount = _money(row.amount_safe_to_pay, "amount_safe_to_pay")
    if safe_amount > request.requested_amount:
        raise ValidationError("amount_safe_to_pay exceeds requested_amount")
    if row.affordability_status not in AFFORDABILITY_STATUSES:
        raise ValidationError("invalid affordability_status")
    if row.recommended_payment_method not in PAYMENT_METHODS:
        raise ValidationError("invalid recommended_payment_method")
    if not isinstance(row.earliest_date_for_full_payment, (date, type(None))):
        raise ValidationError("earliest_date_for_full_payment must be a date or None")
    if row.earliest_date_for_full_payment is not None:
        if not request.request_date <= row.earliest_date_for_full_payment <= request.request_date + timedelta(days=90):
            raise ValidationError("earliest_date_for_full_payment is outside the forecast window")
    if not isinstance(row.decision_explanation, str) or not row.decision_explanation.strip():
        raise ValidationError("decision_explanation must be non-empty prose")

    payments = _parse_plan(row.payment_plan)
    if row.affordability_status == "affordable_now":
        if row.recommended_payment_method != "full_payment":
            raise ValidationError("affordable_now must use full_payment")
        if row.earliest_date_for_full_payment != request.request_date:
            raise ValidationError("affordable_now must have earliest date equal to request_date")
    if row.affordability_status == "not_affordable":
        if row.recommended_payment_method != "not_recommended" or payments:
            raise ValidationError("not_affordable must have no recommended payment plan")
        if row.earliest_date_for_full_payment is not None:
            raise ValidationError("not_affordable must leave earliest full-payment date blank")

    method = row.recommended_payment_method
    if method == "not_recommended":
        if payments:
            raise ValidationError("not_recommended must have payment_plan=none")
    elif method == "full_payment":
        if len(payments) != 1 or payments[0] != (request.request_date, request.requested_amount):
            raise ValidationError("full_payment must contain the full request on request_date")
    elif method == "wait":
        if len(payments) != 1 or payments[0][1] != request.requested_amount:
            raise ValidationError("wait must contain one full-request payment")
        if row.earliest_date_for_full_payment != payments[0][0]:
            raise ValidationError("wait payment must equal earliest full-payment date")
        if row.affordability_status != "affordable_later":
            raise ValidationError("wait must have affordable_later status")
    elif method == "partial_payment":
        if row.affordability_status != "affordable_with_plan":
            raise ValidationError("partial_payment must have affordable_with_plan status")
        if not request.allows_partial_payment or len(payments) != 2:
            raise ValidationError("partial_payment requires exactly two payments and permission")
        if payments[0][0] != request.request_date or payments[0][1] != safe_amount:
            raise ValidationError("partial_payment first payment must equal safe amount on request_date")
        if payments[1][1] + payments[0][1] != request.requested_amount:
            raise ValidationError("partial_payment payments must sum to requested_amount")
        if row.earliest_date_for_full_payment != payments[1][0]:
            raise ValidationError("partial_payment remainder must occur on earliest full-payment date")
        if payments[1][0] > request.desired_completion_date:
            raise ValidationError("partial_payment must complete by desired_completion_date")
        if not Decimal("0") < safe_amount < request.requested_amount:
            raise ValidationError("partial_payment safe amount must be strictly between zero and request")
    elif method == "installments":
        if row.affordability_status != "affordable_with_plan":
            raise ValidationError("installments must have affordable_with_plan status")
        if not payments:
            raise ValidationError("installments require a payment plan")
        _validate_installment_schedule(payments, options)
    _validate_spending_changes(row.spending_changes_needed, events_by_id)


def load_output_rows(path: str) -> tuple[OutputRow, ...]:
    """Parse the written CSV back into typed rows for a final validation pass."""
    required = (
        "request_id", "amount_safe_to_pay", "affordability_status",
        "recommended_payment_method", "payment_plan", "earliest_date_for_full_payment",
        "spending_changes_needed", "decision_explanation",
    )
    rows: list[OutputRow] = []
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != required:
            raise ValidationError("output.csv columns do not match the required order")
        for raw in reader:
            try:
                amount = Decimal(raw["amount_safe_to_pay"])
                earliest = (
                    date.fromisoformat(raw["earliest_date_for_full_payment"])
                    if raw["earliest_date_for_full_payment"] else None
                )
            except (KeyError, InvalidOperation, ValueError) as exc:
                raise ValidationError("output.csv contains an invalid typed value") from exc
            rows.append(OutputRow(
                request_id=raw["request_id"],
                amount_safe_to_pay=amount,
                affordability_status=raw["affordability_status"],
                recommended_payment_method=raw["recommended_payment_method"],
                payment_plan=raw["payment_plan"],
                earliest_date_for_full_payment=earliest,
                spending_changes_needed=raw["spending_changes_needed"],
                decision_explanation=raw["decision_explanation"],
            ))
    return tuple(rows)


def validate_output_rows(
    rows: Iterable[OutputRow],
    requests_by_id: Mapping[str, Request],
    payment_options_by_request: Mapping[str, Iterable[PaymentOption]],
    events_by_id: Mapping[str, FinancialEvent],
) -> None:
    rows_list = list(rows)
    expected_ids = set(requests_by_id)
    actual_ids = [row.request_id for row in rows_list]
    if len(actual_ids) != len(set(actual_ids)):
        raise ValidationError("output contains duplicate request_id values")
    if set(actual_ids) != expected_ids:
        raise ValidationError("output request IDs do not exactly match requests.csv")
    errors = []
    for row in rows_list:
        try:
            validate_output_row(
                row,
                requests_by_id[row.request_id],
                payment_options_by_request.get(row.request_id, ()),
                events_by_id,
            )
        except ValidationError as exc:
            errors.append(f"{row.request_id}: {exc}")
    if errors:
        raise ValidationError("; ".join(errors))
