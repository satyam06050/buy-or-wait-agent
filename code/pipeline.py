"""Stage 7 end-to-end deterministic decision pipeline."""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP, localcontext
from itertools import combinations
from pathlib import Path
from typing import Optional

from .decision_engine import (
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
from .explanation_agent import FinalDecision, explain_decision
from .extraction_common import CallLogger, ProviderResponse, Transport
from .forecast import ForecastResult, build_user_forecast
from .ingestion import Dataset, PaymentOption, Request, load_dataset
from .stage5 import Stage5Run, resolved_dataset, run_stage5
from .validator import OutputRow, load_output_rows, validate_output_rows


MONEY_QUANTUM = Decimal("0.01")
FLEXIBLE_CAPABILITIES = frozenset({"reducible", "stoppable", "reducible_or_stoppable"})


OUTPUT_COLUMNS = (
    "request_id", "amount_safe_to_pay", "affordability_status",
    "recommended_payment_method", "payment_plan", "earliest_date_for_full_payment",
    "spending_changes_needed", "decision_explanation",
)


class PipelineError(RuntimeError):
    """Raised when a full run cannot safely produce a validated output."""


@dataclass(frozen=True)
class FullRunResult:
    rows: tuple[OutputRow, ...]
    stage5: Stage5Run
    output_path: Path


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


def _option_is_allowed(option: PaymentOption, request: Request, max_months: Optional[int]) -> bool:
    if option.payment_method != "installments" or max_months is None:
        return False
    if option.number_of_payments < 1 or option.payment_frequency_days is None:
        return option.number_of_payments == 1 and option.first_payment_date <= _add_months(request.request_date, max_months)
    last_date = option.first_payment_date + timedelta(
        days=option.payment_frequency_days * (option.number_of_payments - 1)
    )
    return last_date <= _add_months(request.request_date, max_months)


def _expand_installment_options(
    dataset: Dataset,
    request: Request,
) -> tuple[InstallmentOption, ...]:
    profile = dataset.profiles_by_user[request.user_id]
    if "installments" not in profile.payment_methods_user_will_consider:
        return ()
    if profile.max_installment_months is None:
        return ()
    expanded = []
    for option in dataset.payment_options_by_request.get(request.request_id, ()):
        if not _option_is_allowed(option, request, profile.max_installment_months):
            continue
        payments = []
        current = option.first_payment_date
        for index in range(option.number_of_payments):
            payments.append(Payment(current, option.payment_amount))
            if option.payment_frequency_days is not None and index + 1 < option.number_of_payments:
                current += timedelta(days=option.payment_frequency_days)
        expanded.append(InstallmentOption(
            payment_option_id=option.payment_option_id,
            payment_method=option.payment_method,
            payments=tuple(payments),
            total_payable_amount=option.total_payable_amount,
        ))
    return tuple(expanded)


def _quantize_money(value: Decimal) -> Decimal:
    with localcontext() as context:
        context.prec = max(50, len(value.as_tuple().digits) + 10)
        return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _format_decimal(value: Decimal) -> str:
    value = _quantize_money(value)
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _format_plan(payments: tuple[Payment, ...]) -> str:
    if not payments:
        return "none"
    return "|".join(
        f"{payment.payment_date.isoformat()}:{_format_decimal(payment.amount)}"
        for payment in payments
    )


def _action_fact(selected: CandidatePlan, request: Request) -> str:
    if selected.payment_method == "not_recommended":
        return "Do not make this payment under the available safe plans."
    if selected.payment_method == "wait":
        base = f"Wait and pay the full request on {selected.payments[0].payment_date.isoformat()}."
    elif selected.payment_method == "installments":
        base = f"Use the supplied installment schedule totaling {_format_decimal(selected.total_paid)}."
    elif selected.payment_method == "partial_payment":
        base = (
            f"Pay {_format_decimal(selected.payments[0].amount)} on {request.request_date.isoformat()} "
            f"and complete the remainder on {selected.payments[1].payment_date.isoformat()}."
        )
    else:
        base = "Pay the full request today."
    if selected.spending_changes:
        return base[:-1] + " after these permitted changes: " + ", ".join(selected.spending_changes) + "."
    return base


def _facts_for(
    dataset: Dataset,
    request: Request,
    forecast: ForecastResult,
    selected: CandidatePlan,
    earliest: Optional[date],
) -> tuple[str, ...]:
    facts = [_action_fact(selected, request)]
    debit_items = [
        item for item in forecast.included_items
        if item.direction == "debit" and item.amount > 0 and item.cash_date >= request.request_date
    ]
    if debit_items:
        driver = max(debit_items, key=lambda item: (item.amount, item.cash_date, item.item_id))
        event = dataset.events_by_id.get(driver.original_event_id or "")
        label = event.description if event is not None else f"protected {event.category if event else 'essential'} spending"
        facts.append(
            f"The forecast reserves {_format_decimal(driver.amount)} for {label} on {driver.cash_date.isoformat()}."
        )
    else:
        facts.append("The forecast includes the user’s confirmed future commitments and protected spending.")
    if selected.spending_changes:
        facts.append("The plan requires these permitted changes: " + ", ".join(selected.spending_changes) + ".")
    elif selected.payment_option_id is not None:
        facts.append(f"The selected source payment option is {selected.payment_option_id}.")
    elif earliest is not None:
        facts.append(f"The first baseline date for one safe full payment is {earliest.isoformat()}.")
    else:
        facts.append("The full request is not safe within the 90-day forecast without changing the baseline spending.")
    return tuple(facts[:4])


def _final_decision_from_row(row: OutputRow, request: Request) -> FinalDecision:
    return FinalDecision(
        request_id=row.request_id,
        requested_amount=request.requested_amount,
        amount_safe_to_pay=row.amount_safe_to_pay,
        affordability_status=row.affordability_status,
        recommended_payment_method=row.recommended_payment_method,
        payment_plan=row.payment_plan,
        earliest_date_for_full_payment=row.earliest_date_for_full_payment,
        spending_changes_needed=row.spending_changes_needed,
    )


def _offline_explanation_transport(body: dict) -> ProviderResponse:
    """Explicit development-only transport for exercising Stage 7 offline."""
    payload = json.loads(body["messages"][1]["content"])
    facts = payload["SUPPORTING_FACTS"]
    return ProviderResponse(
        {"text": " ".join(facts[:2])},
        input_tokens=None,
        output_tokens=None,
    )


def _eligible_spending_actions(
    dataset: Dataset,
    request: Request,
    forecast: ForecastResult,
) -> tuple[tuple[SpendingChange, str], ...]:
    profile = dataset.profiles_by_user[request.user_id]
    forecast_event_ids = {
        item.original_event_id
        for item in forecast.included_items
        if item.original_event_id is not None
    }
    actions: list[tuple[SpendingChange, str]] = []
    for event in dataset.events_by_user.get(request.user_id, ()):
        if (
            event.event_id not in forecast_event_ids
            or event.amount is None
            or event.direction != "debit"
            or event.flexibility not in FLEXIBLE_CAPABILITIES
        ):
            continue
        if (
            event.flexibility in {"stoppable", "reducible_or_stoppable"}
            and event.category in profile.expense_categories_user_is_willing_to_stop
        ):
            change = SpendingChange(event.event_id, "stop", event.amount, Decimal("0"))
            actions.append((change, f"stop:{event.event_id}"))
        if (
            event.flexibility in {"reducible", "reducible_or_stoppable"}
            and event.category in profile.expense_categories_user_is_willing_to_reduce
            and event.minimum_allowed_amount is not None
            and event.minimum_allowed_amount < event.amount
        ):
            change = SpendingChange(
                event.event_id, "reduce_to", event.amount, event.minimum_allowed_amount
            )
            actions.append((
                change,
                f"reduce_to:{event.event_id}:{_format_decimal(event.minimum_allowed_amount)}",
            ))
    return tuple(actions)


def _curve_after_changes(
    forecast: ForecastResult,
    changes: tuple[SpendingChange, ...],
) -> dict[date, Decimal]:
    curve = dict(forecast.baseline_curve)
    by_event = {change.event_id: change for change in changes}
    for item in forecast.included_items:
        change = by_event.get(item.original_event_id or "")
        if change is None or item.direction != "debit" or change.original_amount == 0:
            continue
        release = item.amount * (change.original_amount - change.new_amount) / change.original_amount
        for curve_date in curve:
            if curve_date >= item.cash_date:
                curve[curve_date] += release
    return curve


def _candidate_plans_with_spending_changes(
    dataset: Dataset,
    request: Request,
    forecast: ForecastResult,
    baseline_safe_amount: Decimal,
    base_candidates: list[CandidatePlan],
) -> list[CandidatePlan]:
    actions = _eligible_spending_actions(dataset, request, forecast)
    candidates = list(base_candidates)
    for count in range(1, min(3, len(actions)) + 1):
        for selected_actions in combinations(actions, count):
            changes = tuple(action[0] for action in selected_actions)
            if len({change.event_id for change in changes}) != len(changes):
                continue
            spending_changes(baseline_safe_amount, changes)
            changed_curve = _curve_after_changes(forecast, changes)
            changed_candidates = generate_candidate_plans(
                changed_curve,
                request.requested_amount,
                dataset.profiles_by_user[request.user_id].minimum_balance_to_keep,
                request.request_date,
                request.desired_completion_date,
                request.allows_partial_payment,
                dataset.profiles_by_user[request.user_id].payment_methods_user_will_consider,
                _expand_installment_options(dataset, request),
            )
            labels = tuple(action[1] for action in selected_actions)
            for candidate in changed_candidates:
                # amount_safe_to_pay is frozen before optional changes. A
                # changed-curve partial candidate would use a different first
                # payment, so only use changed curves for full/installment/wait.
                if candidate.payment_method == "not_recommended":
                    continue
                if candidate.payment_method == "partial_payment":
                    # The changed curve may make the completion date safe,
                    # but the first payment remains the frozen baseline safe
                    # amount required by the output contract.
                    payments = (
                        Payment(request.request_date, baseline_safe_amount),
                        Payment(
                            candidate.payments[1].payment_date,
                            request.requested_amount - baseline_safe_amount,
                        ),
                    )
                    candidate = replace(candidate, payments=payments)
                if candidate.safe:
                    candidates.append(replace(candidate, spending_changes=labels))
    return candidates


def build_output_rows(
    dataset: Dataset,
    *,
    explanation_transport: Optional[Transport] = None,
    explanation_cache_dir: str | Path = "cache/stage6/explanations",
    call_logger: Optional[CallLogger] = None,
    explanation_model: str = "deepseek-chat",
) -> tuple[OutputRow, ...]:
    """Build all decision rows from an already-resolved dataset."""
    rows = []
    for request in dataset.requests:
        profile = dataset.profiles_by_user[request.user_id]
        forecast = build_user_forecast(dataset, request.user_id, request.request_date)
        safe_amount_raw = amount_safe_to_pay(
            forecast.baseline_curve,
            request.requested_amount,
            profile.minimum_balance_to_keep,
        )
        safe_amount = _quantize_money(safe_amount_raw)
        earliest = earliest_date_for_full_payment(
            forecast.baseline_curve,
            request.requested_amount,
            profile.minimum_balance_to_keep,
            forecast.window_end,
        )
        base_candidates = generate_candidate_plans(
            forecast.baseline_curve,
            request.requested_amount,
            profile.minimum_balance_to_keep,
            request.request_date,
            request.desired_completion_date,
            request.allows_partial_payment,
            profile.payment_methods_user_will_consider,
            _expand_installment_options(dataset, request),
        )
        candidates = _candidate_plans_with_spending_changes(
            dataset, request, forecast, safe_amount_raw, base_candidates
        )
        selected = rank_and_select(candidates)
        status = selected.affordability_status
        if selected.spending_changes and status == "affordable_now":
            status = "affordable_with_plan"
        # No safe eligible plan exists when the ranker returns the fallback.
        # Keep the status/date pair internally consistent: a non-empty
        # earliest date describes capacity, not an eligible recommendation.
        reported_earliest = None if status == "not_affordable" else earliest
        normalized_payments = tuple(
            Payment(payment.payment_date, _quantize_money(payment.amount))
            for payment in selected.payments
        )
        row = OutputRow(
            request_id=request.request_id,
            amount_safe_to_pay=safe_amount,
            affordability_status=status,
            recommended_payment_method=selected.payment_method,
            payment_plan=_format_plan(normalized_payments),
            earliest_date_for_full_payment=reported_earliest,
            spending_changes_needed="|".join(selected.spending_changes) if selected.spending_changes else "none",
            decision_explanation="",
        )
        explanation = explain_decision(
            _final_decision_from_row(row, request),
            _facts_for(dataset, request, forecast, replace(selected, payments=normalized_payments), reported_earliest),
            transport=explanation_transport,
            cache_dir=explanation_cache_dir,
            call_logger=call_logger,
            model=explanation_model,
        )
        rows.append(OutputRow(**{**row.__dict__, "decision_explanation": explanation.explanation}))
    return tuple(rows)


def write_output_csv(rows: tuple[OutputRow, ...], path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "request_id": row.request_id,
                "amount_safe_to_pay": _format_decimal(row.amount_safe_to_pay),
                "affordability_status": row.affordability_status,
                "recommended_payment_method": row.recommended_payment_method,
                "payment_plan": row.payment_plan,
                "earliest_date_for_full_payment": (
                    row.earliest_date_for_full_payment.isoformat()
                    if row.earliest_date_for_full_payment is not None else ""
                ),
                "spending_changes_needed": row.spending_changes_needed,
                "decision_explanation": row.decision_explanation,
            })
    temporary.replace(output)
    return output


def run_full_pipeline(
    *,
    dataset_dir: str | Path = "dataset",
    output_path: str | Path = "output.csv",
    stage5_cache_dir: str | Path = "cache/stage5",
    explanation_cache_dir: str | Path = "cache/stage6/explanations",
    call_log_path: str | Path = "evaluation/call_log.jsonl",
    rejection_log_path: str | Path = "evaluation/resolution_log.jsonl",
    stage5_run: Optional[Stage5Run] = None,
    explanation_transport: Optional[Transport] = None,
    explanation_model: str = "deepseek-chat",
    allow_unresolved_evidence: bool = False,
) -> FullRunResult:
    dataset = load_dataset(dataset_dir)
    if stage5_run is None:
        stage5_run = run_stage5(
            dataset,
            dataset_root=dataset_dir,
            cache_dir=stage5_cache_dir,
            call_log_path=call_log_path,
            rejection_log_path=rejection_log_path,
        )
    if stage5_run.unresolved and not allow_unresolved_evidence:
        unresolved = ", ".join(item.event_id for item in stage5_run.unresolved)
        raise PipelineError(f"unresolved evidence remains: {unresolved}")
    resolved = resolved_dataset(dataset, stage5_run)
    logger = CallLogger(call_log_path)
    rows = build_output_rows(
        resolved,
        explanation_transport=explanation_transport,
        explanation_cache_dir=explanation_cache_dir,
        call_logger=logger,
        explanation_model=explanation_model,
    )
    validate_output_rows(
        rows,
        resolved.requests_by_id,
        resolved.payment_options_by_request,
        resolved.events_by_id,
    )
    output = write_output_csv(rows, output_path)
    written_rows = load_output_rows(str(output))
    validate_output_rows(
        written_rows,
        resolved.requests_by_id,
        resolved.payment_options_by_request,
        resolved.events_by_id,
    )
    return FullRunResult(rows=written_rows, stage5=stage5_run, output_path=output)


__all__ = [
    "FullRunResult", "PipelineError", "build_output_rows", "run_full_pipeline",
    "write_output_csv", "_offline_explanation_transport",
]
