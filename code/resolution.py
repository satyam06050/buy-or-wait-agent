"""Deterministic merge and diff-check for Stage 5 proposals."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Iterable, Optional

from .extraction_agent_text import TextChange
from .extraction_agent_vision import VisionChange
from .ingestion import FinancialEvent


ALLOWED_TEXT_FIELDS = frozenset({"amount", "status", "settlement_date", "event_date", "currency"})
ALLOWED_STATUSES = frozenset({"settled", "pending", "scheduled", "failed", "cancelled", "unrealized"})


@dataclass(frozen=True)
class ResolutionRejection:
    path: str
    event_id: str
    reason: str
    source: str = ""


@dataclass(frozen=True)
class UnresolvedEvidence:
    event_id: str
    reason: str
    source: str = ""


@dataclass(frozen=True)
class ResolutionResult:
    events: tuple[FinancialEvent, ...]
    applied_text: tuple[TextChange, ...]
    applied_vision: tuple[VisionChange, ...]
    rejections: tuple[ResolutionRejection, ...]
    unresolved: tuple[UnresolvedEvidence, ...]

    @property
    def events_by_id(self) -> dict[str, FinancialEvent]:
        return {event.event_id: event for event in self.events}


def _parse_text_value(field: str, value: str):
    if field == "amount":
        try:
            parsed = Decimal(value.strip().replace(",", ""))
        except InvalidOperation as exc:
            raise ValueError("amount is not a decimal") from exc
        if not parsed.is_finite() or parsed < 0:
            raise ValueError("amount must be finite and non-negative")
        return parsed
    if field in {"event_date", "settlement_date"}:
        try:
            return date.fromisoformat(value.strip())
        except ValueError as exc:
            raise ValueError("date must be YYYY-MM-DD") from exc
    if field == "status":
        if value not in ALLOWED_STATUSES:
            raise ValueError("unsupported event status")
        return value
    if field == "currency":
        if len(value.strip()) != 3 or not value.strip().isalpha():
            raise ValueError("currency must be a three-letter code")
        return value.strip().upper()
    raise ValueError("field is not amendable")


def apply_resolutions(
    original_events: Iterable[FinancialEvent],
    text_changes: Iterable[TextChange],
    vision_changes: Iterable[VisionChange],
    *,
    valid_message_ids: Optional[set[str]] = None,
) -> ResolutionResult:
    """Apply only cited, type-valid proposals and report every rejection.

    The same function validates both modalities. Blank amounts remain unresolved
    unless a separate vision proposal passes all image-evidence checks.
    """
    current = {event.event_id: event for event in original_events}
    original = dict(current)
    rejections: list[ResolutionRejection] = []
    unresolved: list[UnresolvedEvidence] = []
    applied_text: list[TextChange] = []
    applied_vision: list[VisionChange] = []

    for change in text_changes:
        source = change.source_message_id
        if not source or (valid_message_ids is not None and source not in valid_message_ids):
            rejections.append(ResolutionRejection("text", change.event_id, "missing_or_unknown_source_message", source))
            continue
        if change.event_id not in current:
            rejections.append(ResolutionRejection("text", change.event_id, "unknown_event", source))
            continue
        if change.status != "confirmed":
            rejections.append(ResolutionRejection("text", change.event_id, "change_not_confirmed", source))
            continue
        if change.field not in ALLOWED_TEXT_FIELDS:
            rejections.append(ResolutionRejection("text", change.event_id, "field_not_amendable", source))
            continue
        try:
            parsed = _parse_text_value(change.field, change.new_value)
        except ValueError as exc:
            rejections.append(ResolutionRejection("text", change.event_id, str(exc), source))
            continue
        current[change.event_id] = replace(current[change.event_id], **{change.field: parsed})
        applied_text.append(change)

    vision_by_event: dict[str, VisionChange] = {}
    for change in vision_changes:
        if change.event_id in vision_by_event:
            rejections.append(ResolutionRejection("vision", change.event_id, "duplicate_vision_change", change.source_label))
            continue
        vision_by_event[change.event_id] = change
        event = current.get(change.event_id)
        if event is None:
            rejections.append(ResolutionRejection("vision", change.event_id, "unknown_event", change.source_label))
            continue
        if event.amount is not None:
            rejections.append(ResolutionRejection("vision", change.event_id, "event_amount_is_not_blank", change.source_label))
            continue
        if not change.source_label:
            rejections.append(ResolutionRejection("vision", change.event_id, "missing_source_label", change.source_label))
            unresolved.append(UnresolvedEvidence(change.event_id, "missing_source_label", change.source_label))
            continue
        if change.currency_conflict_flag:
            rejections.append(ResolutionRejection("vision", change.event_id, "currency_conflict", change.source_label))
            unresolved.append(UnresolvedEvidence(change.event_id, "currency_conflict", change.source_label))
            continue
        if change.confidence not in {"high", "medium"}:
            rejections.append(ResolutionRejection("vision", change.event_id, "low_or_invalid_confidence", change.source_label))
            unresolved.append(UnresolvedEvidence(change.event_id, "low_or_invalid_confidence", change.source_label))
            continue
        if change.extracted_amount is None:
            rejections.append(ResolutionRejection("vision", change.event_id, "missing_extracted_amount", change.source_label))
            unresolved.append(UnresolvedEvidence(change.event_id, "missing_extracted_amount", change.source_label))
            continue
        if not change.extracted_amount.is_finite() or change.extracted_amount < 0:
            rejections.append(ResolutionRejection("vision", change.event_id, "invalid_extracted_amount", change.source_label))
            unresolved.append(UnresolvedEvidence(change.event_id, "invalid_extracted_amount", change.source_label))
            continue
        current[change.event_id] = replace(event, amount=change.extracted_amount)
        applied_vision.append(change)

    resolved_vision_ids = {change.event_id for change in applied_vision}
    for event in original.values():
        if event.amount is None and event.event_id not in resolved_vision_ids:
            if not any(item.event_id == event.event_id for item in unresolved):
                unresolved.append(UnresolvedEvidence(event.event_id, "no_accepted_vision_resolution"))

    return ResolutionResult(
        events=tuple(current[event_id] for event_id in sorted(current)),
        applied_text=tuple(applied_text),
        applied_vision=tuple(applied_vision),
        rejections=tuple(rejections),
        unresolved=tuple(unresolved),
    )
