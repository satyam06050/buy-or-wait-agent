"""Deterministic 90-day forecast engine wired to the real dataset.

Stage 4 uses the Stage 1 recurrence finding: stable same-user obligations
with a supported monthly cadence (28–31 days) may be projected. It also
reserves known future debits, counts confirmed future salary/settled credits,
converts event amounts with exact dated rates, and excludes unsupported cash
states. Blank amounts are reported and never treated as zero.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable, Optional

from .currency import CurrencyConverter, MissingExchangeRateError
from .decision_engine import BalanceCurve
from .ingestion import Dataset, FinancialEvent


MONTHLY_INTERVALS = frozenset(range(27, 32))
STABLE_DEBIT_EVENT_TYPES = frozenset({"subscription", "debt_payment"})
STABLE_DEBIT_CATEGORIES = frozenset(
    {"rent", "housing", "utilities", "education", "insurance"}
)


@dataclass(frozen=True)
class ForecastItem:
    """A signed cash-flow item included in the forecast."""

    item_id: str
    cash_date: date
    amount: Decimal
    direction: str
    source: str
    original_event_id: Optional[str] = None

    @property
    def signed_amount(self) -> Decimal:
        return self.amount if self.direction == "credit" else -self.amount


@dataclass(frozen=True)
class ExcludedForecastEvent:
    event_id: str
    reason: str


@dataclass(frozen=True)
class BlankAmountEvent:
    event_id: str
    user_id: str
    event_date: date
    settlement_date: Optional[date]


@dataclass(frozen=True)
class ForecastResult:
    user_id: str
    request_date: date
    window_end: date
    baseline_curve: BalanceCurve
    included_items: tuple[ForecastItem, ...]
    excluded_events: tuple[ExcludedForecastEvent, ...]
    blank_amount_events: tuple[BlankAmountEvent, ...]
    conversion_gaps: tuple[ExcludedForecastEvent, ...]

    @property
    def minimum_projected_balance(self) -> Decimal:
        return min(self.baseline_curve.values())


def blank_amount_events(dataset: Dataset) -> tuple[BlankAmountEvent, ...]:
    """Return every blank-amount event in the dataset for Stage 5 handoff."""
    return tuple(
        BlankAmountEvent(
            event_id=event.event_id,
            user_id=event.user_id,
            event_date=event.event_date,
            settlement_date=event.settlement_date,
        )
        for event in dataset.events
        if event.amount is None
    )


def _add_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    year, zero_month = divmod(month_index, 12)
    month = zero_month + 1
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    last_day = (next_month - timedelta(days=1)).day
    return date(year, month, min(value.day, last_day))


def _cash_date(event: FinancialEvent) -> date:
    return event.settlement_date or event.event_date


def _group_key(event: FinancialEvent) -> tuple[str, str, str, str, str]:
    return (
        event.event_type,
        event.category,
        event.description,
        event.direction,
        event.currency,
    )


def _is_stable_debit(event: FinancialEvent) -> bool:
    return (
        event.direction == "debit"
        and (
            event.event_type in STABLE_DEBIT_EVENT_TYPES
            or event.category in STABLE_DEBIT_CATEGORIES
        )
    )


def _is_stable_salary(event: FinancialEvent) -> bool:
    if event.direction != "credit" or event.category != "salary":
        return False
    description = event.description.lower()
    # Regular payroll labels are eligible for one next confirmed salary.
    # Payouts, commissions, bonuses, and contracts are intentionally excluded
    # because Stage 1 found those income histories irregular or conditional.
    return "salary" in description or "payroll" in description


def _has_monthly_signal(events: Iterable[FinancialEvent], request_date: date) -> bool:
    dates = sorted(
        {
            _cash_date(event)
            for event in events
            if event.status == "settled" and _cash_date(event) < request_date
        }
    )
    intervals = [
        (later - earlier).days for earlier, later in zip(dates, dates[1:])
    ]
    recent = intervals[-3:]
    return len(recent) >= 2 and all(interval in MONTHLY_INTERVALS for interval in recent)


def _is_duplicate_linked_debit(event: FinancialEvent, events_by_id: dict[str, FinancialEvent]) -> bool:
    """Identify a later pending/settled duplicate of an earlier settled debit."""
    if not event.linked_event_id or event.direction != "debit":
        return False
    earlier = events_by_id.get(event.linked_event_id)
    return bool(
        earlier
        and earlier.direction == event.direction
        and earlier.amount == event.amount
        and earlier.currency == event.currency
        and earlier.status == "settled"
        and event.status in {"pending", "settled"}
    )


def _convert_to_home(
    event: FinancialEvent,
    amount: Decimal,
    home_currency: str,
    converter: CurrencyConverter,
    cash_date: date,
) -> Decimal:
    return converter.convert(amount, event.currency, home_currency, cash_date)


def _explicit_event_reason(
    event: FinancialEvent,
    events_by_id: dict[str, FinancialEvent],
    request_date: date,
) -> Optional[str]:
    if event.status in {"failed", "cancelled"}:
        return f"status_{event.status}"
    if event.status == "unrealized" or event.direction == "non_cash":
        return "unrealized_non_cash"
    if _is_duplicate_linked_debit(event, events_by_id):
        return "duplicate_linked_debit"
    if event.direction == "credit" and event.status == "pending":
        return "pending_credit"
    if event.status not in {"settled", "pending", "scheduled"}:
        return f"unsupported_status_{event.status}"
    if event.direction == "credit" and event.status == "scheduled":
        if not _is_stable_salary(event):
            return "unconfirmed_scheduled_credit"
    if event.direction == "credit" and event.status == "pending":
        return "pending_credit"
    cash_date = _cash_date(event)
    if cash_date <= request_date:
        return "already_reflected_at_request_date"
    return None


def _append_recurring_items(
    dataset: Dataset,
    user_events: list[FinancialEvent],
    request_date: date,
    window_end: date,
    home_currency: str,
    converter: CurrencyConverter,
    explicit_group_dates: set[tuple[tuple[str, str, str, str, str], date]],
    included: list[ForecastItem],
    excluded: list[ExcludedForecastEvent],
    allow_inferred_salary: bool,
) -> None:
    groups: dict[tuple[str, str, str, str, str], list[FinancialEvent]] = defaultdict(list)
    for event in user_events:
        if event.amount is not None:
            groups[_group_key(event)].append(event)

    for key, group in groups.items():
        representative = max(
            (
                event
                for event in group
                if event.status == "settled" and _cash_date(event) < request_date
            ),
            key=lambda event: (_cash_date(event), event.event_id),
            default=None,
        )
        if representative is None or not _has_monthly_signal(group, request_date):
            continue
        is_debit = _is_stable_debit(representative)
        is_salary = _is_stable_salary(representative) and allow_inferred_salary
        if not (is_debit or is_salary):
            continue

        next_date = _add_months(_cash_date(representative), 1)
        occurrence = 1
        max_occurrences = 1 if is_salary else None
        while next_date <= window_end and (max_occurrences is None or occurrence <= max_occurrences):
            if next_date > request_date and (key, next_date) not in explicit_group_dates:
                item_id = f"recurring:{representative.event_id}:{occurrence}"
                try:
                    amount = _convert_to_home(
                        representative,
                        representative.amount or Decimal("0"),
                        home_currency,
                        converter,
                        next_date,
                    )
                except MissingExchangeRateError as exc:
                    excluded.append(ExcludedForecastEvent(item_id, str(exc)))
                else:
                    included.append(
                        ForecastItem(
                            item_id=item_id,
                            cash_date=next_date,
                            amount=amount,
                            direction=representative.direction,
                            source=(
                                "next_confirmed_salary_from_monthly_history"
                                if is_salary
                                else "recurring_monthly"
                            ),
                            original_event_id=representative.event_id,
                        )
                    )
            occurrence += 1
            next_date = _add_months(_cash_date(representative), occurrence)


def _append_essential_variable_spending(
    user_events: list[FinancialEvent],
    profile_categories: tuple[str, ...],
    request_date: date,
    window_end: date,
    stable_event_ids: set[str],
    included: list[ForecastItem],
) -> None:
    """Carry forward the highest observed 30-day protected-category spend.

    This is a conservative deterministic allowance for essential variable
    spending. Stable monthly obligations are excluded from the buckets so
    they are not counted twice by the recurring projection.
    """
    for category in profile_categories:
        buckets = [Decimal("0"), Decimal("0"), Decimal("0")]
        for event in user_events:
            if (
                event.event_id in stable_event_ids
                or event.amount is None
                or event.status != "settled"
                or event.direction != "debit"
                or event.category != category
            ):
                continue
            days_ago = (request_date - _cash_date(event)).days
            if 1 <= days_ago <= 90:
                buckets[min((days_ago - 1) // 30, 2)] += event.amount
        daily_amount = max(buckets, default=Decimal("0")) / Decimal("30")
        if daily_amount <= 0:
            continue
        cursor = request_date + timedelta(days=1)
        while cursor <= window_end:
            included.append(
                ForecastItem(
                    item_id=f"essential_variable:{category}:{cursor.isoformat()}",
                    cash_date=cursor,
                    amount=daily_amount,
                    direction="debit",
                    source="essential_variable_recent_30_day_max",
                )
            )
            cursor += timedelta(days=1)


def build_user_forecast(
    dataset: Dataset,
    user_id: str,
    request_date: date,
    horizon_days: int = 90,
) -> ForecastResult:
    """Build one user's baseline balance curve for the next 90 days."""
    if horizon_days < 0:
        raise ValueError("horizon_days must be non-negative")
    if user_id not in dataset.profiles_by_user:
        raise KeyError(f"unknown user_id: {user_id}")

    profile = dataset.profiles_by_user[user_id]
    window_end = request_date + timedelta(days=horizon_days)
    user_events = dataset.events_by_user.get(user_id, [])
    events_by_id = dataset.events_by_id
    converter = CurrencyConverter.from_rates(dataset.exchange_rates)
    blank_events = tuple(
        BlankAmountEvent(event.event_id, event.user_id, event.event_date, event.settlement_date)
        for event in user_events
        if event.amount is None
    )

    included: list[ForecastItem] = []
    excluded: list[ExcludedForecastEvent] = []
    conversion_gaps: list[ExcludedForecastEvent] = []
    explicit_group_dates: set[tuple[tuple[str, str, str, str, str], date]] = set()
    stable_event_ids: set[str] = {
        event.event_id
        for event in user_events
        if event.amount is not None and _is_stable_debit(event)
    }

    for event in user_events:
        if event.amount is None:
            excluded.append(ExcludedForecastEvent(event.event_id, "blank_amount_pending_stage_5"))
            continue
        reason = _explicit_event_reason(event, events_by_id, request_date)
        cash_date = _cash_date(event)
        if reason is not None:
            if reason == "already_reflected_at_request_date":
                continue
            excluded.append(ExcludedForecastEvent(event.event_id, reason))
            continue
        if cash_date > window_end:
            continue
        explicit_group_dates.add((_group_key(event), cash_date))
        if _is_stable_debit(event):
            stable_event_ids.add(event.event_id)
        try:
            amount = _convert_to_home(
                event,
                event.amount,
                profile.home_currency,
                converter,
                cash_date,
            )
        except MissingExchangeRateError as exc:
            conversion_gaps.append(ExcludedForecastEvent(event.event_id, str(exc)))
            continue
        included.append(
            ForecastItem(
                item_id=event.event_id,
                cash_date=cash_date,
                amount=amount,
                direction=event.direction,
                source="explicit_future_event",
                original_event_id=event.event_id,
            )
        )

    blank_salary_before_request = any(
        event.amount is None
        and event.category == "salary"
        and _cash_date(event) <= request_date
        for event in user_events
    )
    _append_recurring_items(
        dataset,
        user_events,
        request_date,
        window_end,
        profile.home_currency,
        converter,
        explicit_group_dates,
        included,
        excluded,
        allow_inferred_salary=not blank_salary_before_request,
    )
    _append_essential_variable_spending(
        user_events,
        profile.expense_categories_to_protect,
        request_date,
        window_end,
        stable_event_ids,
        included,
    )

    flows: dict[date, Decimal] = defaultdict(Decimal)
    for item in included:
        flows[item.cash_date] += item.signed_amount

    balance = profile.current_available_balance
    curve: dict[date, Decimal] = {}
    cursor = request_date
    while cursor <= window_end:
        if cursor != request_date:
            balance += flows[cursor]
        curve[cursor] = balance
        cursor += timedelta(days=1)

    return ForecastResult(
        user_id=user_id,
        request_date=request_date,
        window_end=window_end,
        baseline_curve=curve,
        included_items=tuple(sorted(included, key=lambda item: (item.cash_date, item.item_id))),
        excluded_events=tuple(excluded),
        blank_amount_events=blank_events,
        conversion_gaps=tuple(conversion_gaps),
    )


def build_sample_forecasts(dataset: Dataset, sample_limit: int = 5) -> list[ForecastResult]:
    """Build forecasts for the first solved samples for Stage 4 comparison."""
    return [
        build_user_forecast(dataset, sample.user_id, sample.request_date)
        for sample in dataset.sample_requests[:sample_limit]
    ]
