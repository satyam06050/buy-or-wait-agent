"""Stage 5 orchestration for text/image evidence resolution."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Optional

from .extraction_agent_text import TextChange, extract_user_messages, plausible_messages
from .extraction_agent_vision import VisionChange, VisionExtractionResult, extract_all_images
from .extraction_common import (
    CallLogger,
    ProviderError,
    deepseek_transport,
    gemini_transport,
    load_dotenv,
    secret_from_env,
)
from .ingestion import Dataset, FinancialEvent
from .resolution import ResolutionResult, UnresolvedEvidence, apply_resolutions


@dataclass(frozen=True)
class Stage5Run:
    resolution: ResolutionResult
    text_user_count: int
    vision_event_count: int
    text_errors: tuple[tuple[str, str], ...]
    vision_errors: tuple[tuple[str, str], ...]
    vision_results: tuple[VisionExtractionResult, ...]

    @property
    def unresolved(self) -> tuple[UnresolvedEvidence, ...]:
        return self.resolution.unresolved


def _write_rejection_log(path: str | Path, resolution: ResolutionResult) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("a", encoding="utf-8") as handle:
        for rejection in resolution.rejections:
            handle.write(json.dumps({
                "path": rejection.path,
                "event_id": rejection.event_id,
                "reason": rejection.reason,
                "source": rejection.source,
            }, sort_keys=True) + "\n")


def _image_rows(dataset: Dataset, dataset_root: Path) -> tuple[tuple[FinancialEvent, str, Path], ...]:
    rows = []
    for event in dataset.events:
        if event.amount is not None:
            continue
        images = dataset.images_by_event.get(event.event_id, [])
        if not images:
            continue
        image = images[0]
        rows.append((event, image.image_id, dataset_root / "media" / "images" / f"{image.image_id}.png"))
    return tuple(rows)


def run_stage5(
    dataset: Dataset,
    *,
    dataset_root: str | Path = "dataset",
    cache_dir: str | Path = "cache/stage5",
    call_log_path: str | Path = "evaluation/call_log.jsonl",
    rejection_log_path: str | Path = "evaluation/resolution_log.jsonl",
    deepseek_transport_override=None,
    gemini_transport_override=None,
    deepseek_model: Optional[str] = None,
    gemini_model: Optional[str] = None,
) -> Stage5Run:
    """Run both independent extraction paths and merge only accepted evidence."""
    load_dotenv()
    text_model = deepseek_model or os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
    vision_model = gemini_model or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    logger = CallLogger(call_log_path)

    text_transport = deepseek_transport_override
    if text_transport is None:
        text_transport = deepseek_transport(api_key=secret_from_env("deepseek_api_key"), model=text_model)
    vision_transport = gemini_transport_override
    if vision_transport is None:
        vision_transport = gemini_transport(api_key=secret_from_env("gemini_api_key"), model=vision_model)

    text_changes: list[TextChange] = []
    text_errors: list[tuple[str, str]] = []
    text_users = 0
    text_provider_unavailable = False
    for user_id, messages in dataset.messages_by_user.items():
        candidates = plausible_messages(messages)
        if not candidates:
            continue
        text_users += 1
        try:
            result = extract_user_messages(
                user_id,
                dataset.events_by_user.get(user_id, ()),
                candidates,
                transport=text_transport,
                cache_dir=Path(cache_dir) / "text",
                call_logger=logger,
                model=text_model,
            )
        except (ProviderError, OSError) as exc:
            error_text = str(exc)
            text_errors.append((user_id, error_text))
            if isinstance(exc, ProviderError):
                logger.append(
                    provider="deepseek", model=text_model, call_site="text_extraction",
                    subject_id=user_id, input_tokens=None, output_tokens=None,
                    error=error_text,
                )
            if any(marker in error_text for marker in ("HTTP 401", "HTTP 402", "HTTP 403")):
                text_provider_unavailable = True
                break
        else:
            text_changes.extend(result.changes)

    vision_rows = _image_rows(dataset, Path(dataset_root))
    vision_results = extract_all_images(
        vision_rows,
        transport=vision_transport,
        cache_dir=Path(cache_dir) / "vision",
        call_logger=logger,
        model=vision_model,
    )
    vision_changes: list[VisionChange] = [
        result.change for result in vision_results if result.change is not None
    ]
    vision_errors = tuple(
        (result.event_id, result.error)
        for result in vision_results
        if result.error is not None
    )

    resolution = apply_resolutions(
        dataset.events,
        text_changes,
        vision_changes,
        valid_message_ids=set(dataset.messages_by_id),
    )
    _write_rejection_log(rejection_log_path, resolution)
    return Stage5Run(
        resolution=resolution,
        text_user_count=text_users,
        vision_event_count=len(vision_rows),
        text_errors=tuple(text_errors),
        vision_errors=vision_errors,
        vision_results=vision_results,
    )


def resolved_dataset(dataset: Dataset, run: Stage5Run) -> Dataset:
    """Return a shallow dataset copy with the accepted ledger changes applied."""
    by_id = run.resolution.events_by_id
    events = [by_id[event.event_id] for event in dataset.events]
    events_by_user = {
        user_id: [by_id[event.event_id] for event in user_events]
        for user_id, user_events in dataset.events_by_user.items()
    }
    return replace(dataset, events=events, events_by_id=by_id, events_by_user=events_by_user)
