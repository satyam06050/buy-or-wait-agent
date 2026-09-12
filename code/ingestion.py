"""CSV ingestion and lookup indices for the Buy or Wait? dataset.

This module deliberately performs normalization only. It does not forecast,
classify events, resolve messages/images, or make financial decisions.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, Optional, TypeVar


T = TypeVar("T")


class IngestionError(ValueError):
    """Raised when a participant-facing CSV cannot be normalized safely."""


@dataclass(frozen=True)
class FinancialProfile:
    user_id: str
    home_currency: str
    current_available_balance: Decimal
    minimum_balance_to_keep: Decimal
    financial_priorities: tuple[str, ...]
    expense_categories_to_protect: tuple[str, ...]
    expense_categories_user_is_willing_to_reduce: tuple[str, ...]
    expense_categories_user_is_willing_to_stop: tuple[str, ...]
    payment_methods_user_will_consider: tuple[str, ...]
    max_installment_months: Optional[int]


@dataclass(frozen=True)
class FinancialEvent:
    event_id: str
    user_id: str
    event_type: str
    description: str
    category: str
    direction: str
    amount: Optional[Decimal]
    currency: str
    event_date: date
    settlement_date: Optional[date]
    status: str
    linked_event_id: Optional[str]
    flexibility: Optional[str]
    minimum_allowed_amount: Optional[Decimal]


@dataclass(frozen=True)
class Request:
    request_id: str
    user_id: str
    request_date: date
    request_type: str
    requested_amount: Decimal
    desired_completion_date: date
    allows_partial_payment: bool
    request_text: str


@dataclass(frozen=True)
class SampleRequest:
    request_id: str
    user_id: str
    request_date: date
    request_type: str
    requested_amount: Decimal
    desired_completion_date: date
    allows_partial_payment: bool
    request_text: str
    amount_safe_to_pay: Decimal
    affordability_status: str
    recommended_payment_method: str
    payment_plan: str
    earliest_date_for_full_payment: Optional[date]
    spending_changes_needed: str
    decision_explanation: str


@dataclass(frozen=True)
class PaymentOption:
    payment_option_id: str
    request_id: str
    payment_method: str
    payment_amount: Decimal
    number_of_payments: int
    first_payment_date: date
    payment_frequency_days: Optional[int]
    financing_fee: Decimal
    total_payable_amount: Decimal


@dataclass(frozen=True)
class Message:
    message_id: str
    user_id: str
    request_id: Optional[str]
    related_event_id: Optional[str]
    sent_at: datetime
    source_type: str
    message_text: str


@dataclass(frozen=True)
class Image:
    image_id: str
    user_id: str
    request_id: Optional[str]
    related_event_id: Optional[str]


@dataclass(frozen=True)
class ExchangeRate:
    rate_date: date
    from_currency: str
    to_currency: str
    rate: Decimal


@dataclass(frozen=True)
class OutputTemplateRow:
    request_id: str
    amount_safe_to_pay: Optional[Decimal]
    affordability_status: Optional[str]
    recommended_payment_method: Optional[str]
    payment_plan: Optional[str]
    earliest_date_for_full_payment: Optional[date]
    spending_changes_needed: Optional[str]
    decision_explanation: Optional[str]


@dataclass
class Dataset:
    """Normalized participant data and indices used by later stages."""

    profiles: list[FinancialProfile]
    events: list[FinancialEvent]
    requests: list[Request]
    sample_requests: list[SampleRequest]
    payment_options: list[PaymentOption]
    messages: list[Message]
    images: list[Image]
    exchange_rates: list[ExchangeRate]
    output_template: list[OutputTemplateRow]

    profiles_by_user: dict[str, FinancialProfile]
    events_by_id: dict[str, FinancialEvent]
    events_by_user: dict[str, list[FinancialEvent]]
    requests_by_id: dict[str, Request]
    sample_requests_by_id: dict[str, SampleRequest]
    payment_options_by_id: dict[str, PaymentOption]
    payment_options_by_request: dict[str, list[PaymentOption]]
    messages_by_id: dict[str, Message]
    messages_by_user: dict[str, list[Message]]
    messages_by_request: dict[str, list[Message]]
    messages_by_event: dict[str, list[Message]]
    images_by_id: dict[str, Image]
    images_by_user: dict[str, list[Image]]
    images_by_request: dict[str, list[Image]]
    images_by_event: dict[str, list[Image]]
    rates_by_key: dict[tuple[date, str, str], ExchangeRate]
    output_template_by_request: dict[str, OutputTemplateRow]


def _required(row: dict[str, str], field: str, source: str, row_number: int) -> str:
    value = row.get(field, "")
    if value is None or value.strip() == "":
        raise IngestionError(f"{source}:{row_number}: required field {field!r} is blank")
    return value.strip()


def _optional(row: dict[str, str], field: str) -> Optional[str]:
    value = row.get(field, "")
    if value is None:
        return None
    value = value.strip()
    return value or None


def _decimal(value: Optional[str], field: str, source: str, row_number: int) -> Optional[Decimal]:
    if value is None or value.strip() == "":
        return None
    try:
        return Decimal(value.strip())
    except InvalidOperation as exc:
        raise IngestionError(
            f"{source}:{row_number}: invalid decimal in {field!r}: {value!r}"
        ) from exc


def _required_decimal(row: dict[str, str], field: str, source: str, row_number: int) -> Decimal:
    value = _decimal(row.get(field), field, source, row_number)
    if value is None:
        raise IngestionError(f"{source}:{row_number}: required decimal {field!r} is blank")
    return value


def _date(value: Optional[str], field: str, source: str, row_number: int) -> Optional[date]:
    if value is None or value.strip() == "":
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise IngestionError(
            f"{source}:{row_number}: invalid ISO date in {field!r}: {value!r}"
        ) from exc


def _required_date(row: dict[str, str], field: str, source: str, row_number: int) -> date:
    value = _date(row.get(field), field, source, row_number)
    if value is None:
        raise IngestionError(f"{source}:{row_number}: required date {field!r} is blank")
    return value


def _datetime(value: Optional[str], field: str, source: str, row_number: int) -> Optional[datetime]:
    if value is None or value.strip() == "":
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise IngestionError(
            f"{source}:{row_number}: invalid ISO timestamp in {field!r}: {value!r}"
        ) from exc


def _required_datetime(row: dict[str, str], field: str, source: str, row_number: int) -> datetime:
    value = _datetime(row.get(field), field, source, row_number)
    if value is None:
        raise IngestionError(f"{source}:{row_number}: required timestamp {field!r} is blank")
    return value


def _bool(value: Optional[str], field: str, source: str, row_number: int) -> bool:
    normalized = (value or "").strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise IngestionError(
        f"{source}:{row_number}: expected true/false in {field!r}, got {value!r}"
    )


def _optional_int(value: Optional[str], field: str, source: str, row_number: int) -> Optional[int]:
    if value is None or value.strip() == "":
        return None
    try:
        return int(value.strip())
    except ValueError as exc:
        raise IngestionError(
            f"{source}:{row_number}: invalid integer in {field!r}: {value!r}"
        ) from exc


def _required_int(row: dict[str, str], field: str, source: str, row_number: int) -> int:
    value = _optional_int(row.get(field), field, source, row_number)
    if value is None:
        raise IngestionError(f"{source}:{row_number}: required integer {field!r} is blank")
    return value


def _split_pipe(value: Optional[str]) -> tuple[str, ...]:
    if value is None or value.strip() == "":
        return ()
    return tuple(part.strip() for part in value.split("|") if part.strip())


def _csv_rows(path: Path) -> Iterable[tuple[int, dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise IngestionError(f"{path}: missing CSV header")
        for row_number, row in enumerate(reader, start=2):
            yield row_number, row


def _assert_unique(rows: Iterable[T], key, source: str) -> None:
    seen: set[object] = set()
    for item in rows:
        identifier = key(item)
        if identifier in seen:
            raise IngestionError(f"{source}: duplicate identifier {identifier!r}")
        seen.add(identifier)


def _load_profiles(path: Path) -> list[FinancialProfile]:
    result = []
    for n, row in _csv_rows(path):
        result.append(
            FinancialProfile(
                user_id=_required(row, "user_id", str(path), n),
                home_currency=_required(row, "home_currency", str(path), n),
                current_available_balance=_required_decimal(row, "current_available_balance", str(path), n),
                minimum_balance_to_keep=_required_decimal(row, "minimum_balance_to_keep", str(path), n),
                financial_priorities=_split_pipe(row.get("financial_priorities")),
                expense_categories_to_protect=_split_pipe(row.get("expense_categories_to_protect")),
                expense_categories_user_is_willing_to_reduce=_split_pipe(row.get("expense_categories_user_is_willing_to_reduce")),
                expense_categories_user_is_willing_to_stop=_split_pipe(row.get("expense_categories_user_is_willing_to_stop")),
                payment_methods_user_will_consider=_split_pipe(row.get("payment_methods_user_will_consider")),
                max_installment_months=_optional_int(row.get("max_installment_months"), "max_installment_months", str(path), n),
            )
        )
    _assert_unique(result, lambda item: item.user_id, str(path))
    return result


def _load_events(path: Path) -> list[FinancialEvent]:
    result = []
    for n, row in _csv_rows(path):
        result.append(
            FinancialEvent(
                event_id=_required(row, "event_id", str(path), n),
                user_id=_required(row, "user_id", str(path), n),
                event_type=_required(row, "event_type", str(path), n),
                description=_required(row, "description", str(path), n),
                category=_required(row, "category", str(path), n),
                direction=_required(row, "direction", str(path), n),
                amount=_decimal(row.get("amount"), "amount", str(path), n),
                currency=_required(row, "currency", str(path), n),
                event_date=_required_date(row, "event_date", str(path), n),
                settlement_date=_date(row.get("settlement_date"), "settlement_date", str(path), n),
                status=_required(row, "status", str(path), n),
                linked_event_id=_optional(row, "linked_event_id"),
                flexibility=_optional(row, "flexibility"),
                minimum_allowed_amount=_decimal(row.get("minimum_allowed_amount"), "minimum_allowed_amount", str(path), n),
            )
        )
    _assert_unique(result, lambda item: item.event_id, str(path))
    return result


def _load_requests(path: Path) -> list[Request]:
    result = []
    for n, row in _csv_rows(path):
        result.append(
            Request(
                request_id=_required(row, "request_id", str(path), n),
                user_id=_required(row, "user_id", str(path), n),
                request_date=_required_date(row, "request_date", str(path), n),
                request_type=_required(row, "request_type", str(path), n),
                requested_amount=_required_decimal(row, "requested_amount", str(path), n),
                desired_completion_date=_required_date(row, "desired_completion_date", str(path), n),
                allows_partial_payment=_bool(row.get("allows_partial_payment"), "allows_partial_payment", str(path), n),
                request_text=_required(row, "request_text", str(path), n),
            )
        )
    _assert_unique(result, lambda item: item.request_id, str(path))
    return result


def _load_sample_requests(path: Path) -> list[SampleRequest]:
    result = []
    for n, row in _csv_rows(path):
        earliest = _date(row.get("earliest_date_for_full_payment"), "earliest_date_for_full_payment", str(path), n)
        safe_amount = _required_decimal(row, "amount_safe_to_pay", str(path), n)
        result.append(
            SampleRequest(
                request_id=_required(row, "request_id", str(path), n),
                user_id=_required(row, "user_id", str(path), n),
                request_date=_required_date(row, "request_date", str(path), n),
                request_type=_required(row, "request_type", str(path), n),
                requested_amount=_required_decimal(row, "requested_amount", str(path), n),
                desired_completion_date=_required_date(row, "desired_completion_date", str(path), n),
                allows_partial_payment=_bool(row.get("allows_partial_payment"), "allows_partial_payment", str(path), n),
                request_text=_required(row, "request_text", str(path), n),
                amount_safe_to_pay=safe_amount,
                affordability_status=_required(row, "affordability_status", str(path), n),
                recommended_payment_method=_required(row, "recommended_payment_method", str(path), n),
                payment_plan=_required(row, "payment_plan", str(path), n),
                earliest_date_for_full_payment=earliest,
                spending_changes_needed=_required(row, "spending_changes_needed", str(path), n),
                decision_explanation=_required(row, "decision_explanation", str(path), n),
            )
        )
    _assert_unique(result, lambda item: item.request_id, str(path))
    return result


def _load_payment_options(path: Path) -> list[PaymentOption]:
    result = []
    for n, row in _csv_rows(path):
        result.append(
            PaymentOption(
                payment_option_id=_required(row, "payment_option_id", str(path), n),
                request_id=_required(row, "request_id", str(path), n),
                payment_method=_required(row, "payment_method", str(path), n),
                payment_amount=_required_decimal(row, "payment_amount", str(path), n),
                number_of_payments=_required_int(row, "number_of_payments", str(path), n),
                first_payment_date=_required_date(row, "first_payment_date", str(path), n),
                payment_frequency_days=_optional_int(row.get("payment_frequency_days"), "payment_frequency_days", str(path), n),
                financing_fee=_required_decimal(row, "financing_fee", str(path), n),
                total_payable_amount=_required_decimal(row, "total_payable_amount", str(path), n),
            )
        )
    _assert_unique(result, lambda item: item.payment_option_id, str(path))
    return result


def _load_messages(path: Path) -> list[Message]:
    result = []
    for n, row in _csv_rows(path):
        result.append(
            Message(
                message_id=_required(row, "message_id", str(path), n),
                user_id=_required(row, "user_id", str(path), n),
                request_id=_optional(row, "request_id"),
                related_event_id=_optional(row, "related_event_id"),
                sent_at=_required_datetime(row, "sent_at", str(path), n),
                source_type=_required(row, "source_type", str(path), n),
                message_text=_required(row, "message_text", str(path), n),
            )
        )
    _assert_unique(result, lambda item: item.message_id, str(path))
    return result


def _load_images(path: Path) -> list[Image]:
    result = []
    for n, row in _csv_rows(path):
        result.append(
            Image(
                image_id=_required(row, "image_id", str(path), n),
                user_id=_required(row, "user_id", str(path), n),
                request_id=_optional(row, "request_id"),
                related_event_id=_optional(row, "related_event_id"),
            )
        )
    _assert_unique(result, lambda item: item.image_id, str(path))
    return result


def _load_exchange_rates(path: Path) -> list[ExchangeRate]:
    result = []
    for n, row in _csv_rows(path):
        result.append(
            ExchangeRate(
                rate_date=_required_date(row, "rate_date", str(path), n),
                from_currency=_required(row, "from_currency", str(path), n),
                to_currency=_required(row, "to_currency", str(path), n),
                rate=_required_decimal(row, "rate", str(path), n),
            )
        )
    _assert_unique(
        result,
        lambda item: (item.rate_date, item.from_currency, item.to_currency),
        str(path),
    )
    return result


def _load_output_template(path: Path) -> list[OutputTemplateRow]:
    result = []
    for n, row in _csv_rows(path):
        result.append(
            OutputTemplateRow(
                request_id=_required(row, "request_id", str(path), n),
                amount_safe_to_pay=_decimal(row.get("amount_safe_to_pay"), "amount_safe_to_pay", str(path), n),
                affordability_status=_optional(row, "affordability_status"),
                recommended_payment_method=_optional(row, "recommended_payment_method"),
                payment_plan=_optional(row, "payment_plan"),
                earliest_date_for_full_payment=_date(row.get("earliest_date_for_full_payment"), "earliest_date_for_full_payment", str(path), n),
                spending_changes_needed=_optional(row, "spending_changes_needed"),
                decision_explanation=_optional(row, "decision_explanation"),
            )
        )
    _assert_unique(result, lambda item: item.request_id, str(path))
    return result


def _append_index(index: dict[str, list[T]], key: Optional[str], value: T) -> None:
    if key is not None:
        index.setdefault(key, []).append(value)


def _build_dataset(dataset_dir: Path) -> Dataset:
    profiles = _load_profiles(dataset_dir / "financial_profiles.csv")
    events = _load_events(dataset_dir / "financial_events.csv")
    requests = _load_requests(dataset_dir / "requests.csv")
    sample_requests = _load_sample_requests(dataset_dir / "sample_requests.csv")
    payment_options = _load_payment_options(dataset_dir / "request_payment_options.csv")
    messages = _load_messages(dataset_dir / "messages.csv")
    images = _load_images(dataset_dir / "images.csv")
    exchange_rates = _load_exchange_rates(dataset_dir / "exchange_rates.csv")
    output_template = _load_output_template(dataset_dir / "output.csv")

    events_by_user: dict[str, list[FinancialEvent]] = {}
    for event in events:
        _append_index(events_by_user, event.user_id, event)

    payment_options_by_request: dict[str, list[PaymentOption]] = {}
    for option in payment_options:
        _append_index(payment_options_by_request, option.request_id, option)

    messages_by_user: dict[str, list[Message]] = {}
    messages_by_request: dict[str, list[Message]] = {}
    messages_by_event: dict[str, list[Message]] = {}
    for message in messages:
        _append_index(messages_by_user, message.user_id, message)
        _append_index(messages_by_request, message.request_id, message)
        _append_index(messages_by_event, message.related_event_id, message)

    images_by_user: dict[str, list[Image]] = {}
    images_by_request: dict[str, list[Image]] = {}
    images_by_event: dict[str, list[Image]] = {}
    for image in images:
        _append_index(images_by_user, image.user_id, image)
        _append_index(images_by_request, image.request_id, image)
        _append_index(images_by_event, image.related_event_id, image)

    return Dataset(
        profiles=profiles,
        events=events,
        requests=requests,
        sample_requests=sample_requests,
        payment_options=payment_options,
        messages=messages,
        images=images,
        exchange_rates=exchange_rates,
        output_template=output_template,
        profiles_by_user={item.user_id: item for item in profiles},
        events_by_id={item.event_id: item for item in events},
        events_by_user=events_by_user,
        requests_by_id={item.request_id: item for item in requests},
        sample_requests_by_id={item.request_id: item for item in sample_requests},
        payment_options_by_id={item.payment_option_id: item for item in payment_options},
        payment_options_by_request=payment_options_by_request,
        messages_by_id={item.message_id: item for item in messages},
        messages_by_user=messages_by_user,
        messages_by_request=messages_by_request,
        messages_by_event=messages_by_event,
        images_by_id={item.image_id: item for item in images},
        images_by_user=images_by_user,
        images_by_request=images_by_request,
        images_by_event=images_by_event,
        rates_by_key={(item.rate_date, item.from_currency, item.to_currency): item for item in exchange_rates},
        output_template_by_request={item.request_id: item for item in output_template},
    )


def load_dataset(dataset_dir: str | Path = "dataset") -> Dataset:
    """Load and normalize every participant-facing CSV in ``dataset_dir``."""
    path = Path(dataset_dir)
    if not path.is_dir():
        raise IngestionError(f"dataset directory does not exist: {path}")
    return _build_dataset(path)
