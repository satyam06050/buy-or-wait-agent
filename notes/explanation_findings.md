# Phase 6 — Explanation agent findings

## Implementation

`code/explanation_agent.py` implements the prose-only explanation boundary:

- `FinalDecision` is a frozen dataclass containing all deterministic decision fields.
- `explain_decision(...)` accepts one final decision and exactly 2–4 deterministic supporting facts.
- The prompt treats the decision object as authoritative and facts/request-like text as data, not instructions.
- The prompt explicitly forbids changing, recalculating, or questioning decision fields.
- The return type is `ExplanationResult`, whose `explanation` field is validated plain `str` prose. The function has no return path for a modified decision.
- Output is limited to one or two concise sentences, without JSON, markdown, bullets, headings, or labels.
- Output is rejected if empty, over 500 characters, JSON-like, bullet-formatted, or longer than two sentences.
- Results are cached by a SHA-256 hash of the final decision, facts, provider, and model.
- Provider calls are logged through the existing metadata-only call logger with `call_site=explanation`.

`code/extraction_common.py` now also provides a separate plain-text DeepSeek transport. It does not use the structured JSON response mode used by Stage 5 extraction.

## Style check

The supplied solved samples use short, factual explanations such as:

- “Pay ZAR 25,256 today. This leaves at least ZAR 18,000 available over the next 90 days.”
- “Wait until 15 June 2024, then pay IDR 12,693,000 in full. Paying sooner would put the IDR 30,686,600 minimum at risk.”
- “Do not make this payment by 12 January 2026. None of the available options keeps the ZAR 13,100 minimum protected.”

The Phase 6 prompt requests the same concise action-plus-safety-fact style without permitting the model to recompute the decision.

## Verification

`tests/test_explanation_agent.py` covers:

- Immutable final decision input and string-only explanation output.
- Prompt scope and fixed decision fields.
- Exactly 2–4 non-empty supporting facts.
- Rejection of JSON, bullets, empty output, and more than two sentences.
- Cache hit behavior with only one provider invocation.
- Five sample-style generated explanations whose method and safe amount come only from the fixed decision object.

Full suite result: **33 tests passed**.

## Provider status

The implementation defaults to DeepSeek `deepseek-chat`, matching the text provider configured for this project. The supplied DeepSeek credential previously returned HTTP 402 Payment Required during Stage 5, so no live Phase 6 call is claimed here. The five explanation spot-checks are offline provider-contract checks using injected deterministic transports; a funded/usable DeepSeek credential is required for live explanation generation.

No deterministic decision field is changed when the provider is unavailable or when prose validation fails. Phase 6 must not advance to the full pipeline until the live explanation provider is available for the required spot-check.

## Gate status

- [x] Explanation agent accepts a final deterministic decision plus 2–4 facts.
- [x] Explanation output is prose-only and cannot alter decision fields.
- [x] Five offline sample-style explanations were spot-checked against fixed decision fields.
- [x] Caching and call-site logging are implemented.
- [ ] Live five-request spot-check is blocked by the supplied DeepSeek HTTP 402 credential failure.
