"""Small provider, cache, and call-log utilities for Stage 5.

This module intentionally uses only the Python standard library. API responses are
parsed into JSON before the provider result reaches the deterministic merge layer.
Secrets and prompts are never written to the call log.
"""
from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional


class ProviderError(RuntimeError):
    """Raised when a provider request or response cannot be used safely."""


@dataclass(frozen=True)
class ProviderResponse:
    payload: dict[str, Any]
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None


Transport = Callable[[dict[str, Any]], ProviderResponse]


def load_dotenv(path: str | Path = ".env") -> None:
    """Load simple KEY=VALUE entries without overriding the process environment."""
    dotenv = Path(path)
    if not dotenv.exists():
        return
    for raw_line in dotenv.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def secret_from_env(name: str) -> str:
    value = os.environ.get(name) or os.environ.get(name.upper())
    if not value:
        raise ProviderError(f"missing API credential environment variable {name}")
    return value


def stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def read_json_cache(path: Path) -> Optional[dict[str, Any]]:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def write_json_cache(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


class CallLogger:
    """Append provider metadata only; never store prompts, keys, or raw evidence."""

    def __init__(self, path: str | Path = "evaluation/call_log.jsonl") -> None:
        self.path = Path(path)

    def append(
        self,
        *,
        provider: str,
        model: str,
        call_site: str,
        subject_id: str,
        input_tokens: Optional[int],
        output_tokens: Optional[int],
        cached: bool = False,
        error: Optional[str] = None,
    ) -> None:
        total = None if input_tokens is None or output_tokens is None else input_tokens + output_tokens
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "provider": provider,
            "model": model,
            "call_site": call_site,
            "subject_id": subject_id,
            "cached": cached,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total,
            "error": error,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def _json_from_response(response: Any) -> dict[str, Any]:
    if not isinstance(response, dict):
        raise ProviderError("provider response is not a JSON object")
    if "error" in response:
        raise ProviderError(f"provider returned an error: {response['error']}")
    return response


def _parse_json_text(text: str) -> dict[str, Any]:
    """Parse strict JSON, tolerating only a provider-added markdown fence."""
    normalized = text.strip()
    if normalized.startswith("```") and normalized.endswith("```"):
        lines = normalized.splitlines()
        normalized = "\n".join(lines[1:-1]).strip()
        if normalized.lower().startswith("json\n"):
            normalized = normalized[5:]
    try:
        value = json.loads(normalized)
    except json.JSONDecodeError:
        start, end = normalized.find("{"), normalized.rfind("}")
        if start < 0 or end <= start:
            raise ProviderError("provider response did not contain JSON")
        try:
            value = json.loads(normalized[start:end + 1])
        except json.JSONDecodeError as exc:
            raise ProviderError("provider response did not contain valid JSON") from exc
    return _json_from_response(value)


def deepseek_transport(
    *,
    api_key: str,
    model: str = "deepseek-chat",
    endpoint: str = "https://api.deepseek.com/chat/completions",
    timeout: int = 120,
) -> Transport:
    """Return an OpenAI-compatible DeepSeek JSON transport."""
    def send(body: dict[str, Any]) -> ProviderResponse:
        request_body = dict(body)
        request_body.setdefault("model", model)
        request_body.setdefault("temperature", 0)
        request_body.setdefault("response_format", {"type": "json_object"})
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(request_body).encode("utf-8"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise ProviderError(f"DeepSeek request failed: HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ProviderError(f"DeepSeek request failed: {type(exc).__name__}") from exc
        raw = _json_from_response(raw)
        try:
            content = raw["choices"][0]["message"]["content"]
            payload = _parse_json_text(content) if isinstance(content, str) else content
            usage = raw.get("usage", {})
            return ProviderResponse(
                payload=_json_from_response(payload),
                input_tokens=usage.get("prompt_tokens"),
                output_tokens=usage.get("completion_tokens"),
            )
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise ProviderError("DeepSeek response did not contain structured JSON") from exc
    return send


def gemini_transport(
    *,
    api_key: str,
    model: str = "gemini-2.0-flash",
    endpoint_root: str = "https://generativelanguage.googleapis.com/v1beta/models",
    timeout: int = 120,
) -> Transport:
    """Return a Gemini generateContent transport for text plus inline PNG data."""
    endpoint = f"{endpoint_root}/{model}:generateContent?key={api_key}"

    def send(body: dict[str, Any]) -> ProviderResponse:
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise ProviderError(f"Gemini request failed: HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ProviderError(f"Gemini request failed: {type(exc).__name__}") from exc
        raw = _json_from_response(raw)
        try:
            parts = raw["candidates"][0]["content"]["parts"]
            text = next(part["text"] for part in parts if "text" in part)
            payload = _parse_json_text(text)
            usage = raw.get("usageMetadata", {})
            return ProviderResponse(
                payload=_json_from_response(payload),
                input_tokens=usage.get("promptTokenCount"),
                output_tokens=usage.get("candidatesTokenCount"),
            )
        except (KeyError, IndexError, StopIteration, TypeError, json.JSONDecodeError) as exc:
            raise ProviderError("Gemini response did not contain structured JSON") from exc
    return send
