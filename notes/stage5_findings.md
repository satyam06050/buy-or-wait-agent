# Stage 5 — Extraction agents and evidence resolution

## Implemented modules

- `code/extraction_common.py`
  - Standard-library HTTPS transports for DeepSeek chat and Gemini `generateContent`.
  - `.env` loading without overriding process variables.
  - Structured JSON parsing, including only a narrow provider-added fenced-JSON normalization.
  - SHA-256 cache keys and atomic JSON caches.
  - Metadata-only `evaluation/call_log.jsonl`; prompts, API keys, raw messages, and images are never logged.
- `code/extraction_agent_text.py`
  - One batched DeepSeek request per message-bearing user.
  - Strict untrusted-message prompt and JSON `TextChange` schema.
  - Only explicit, cited changes to amount/status/event date/settlement date/currency are proposed.
- `code/extraction_agent_vision.py`
  - One Gemini Flash request per linked blank-amount image.
  - Event context includes category, description, direction, and expected currency.
  - Prompt asks for final/net/payable amount, not line items, subtotals, gross pay, deductions, or already-paid amounts.
  - Gemini `gemini-2.5-flash` is used with thinking disabled for bounded structured extraction.
- `code/resolution.py`
  - One deterministic diff-check for both text and vision proposals.
  - Requires a valid `source_message_id` for text or non-empty `source_label` for vision.
  - Rejects unknown fields, invalid dates/statuses/currencies/amounts, low confidence, null amounts, and currency conflicts.
  - Keeps rejected values unchanged and reports unresolved evidence.
- `code/stage5.py`
  - Runs both independent paths, writes sanitized rejection logs, and exposes `resolved_dataset(...)`.
  - Stops repeated text calls after provider-unavailable HTTP 401/402/403 rather than wasting tokens.

## Live provider results

### Vision — Gemini Flash

Gemini 2.5 Flash successfully resolved all **16/16** previously blank events. Every accepted result had high confidence and `currency_conflict_flag=false`; the final resolved ledger contains zero blank amounts.

| Event | Image | Extracted amount | Evidence label |
|---|---|---:|---|
| event_253 | image_01 | 4,365,000 | Net Pay |
| event_1442 | image_02 | 100,000.00 | Balance Due |
| event_1545 | image_03 | 41,272.00 | Cash Paid |
| event_1700 | image_04 | 2,854.00 | Item Bill |
| event_1786 | image_05 | 704.05 | Amount due till |
| event_3051 | image_06 | 1,995.00 | Total |
| event_3231 | image_07 | 8,528.10 | Total |
| event_4535 | image_08 | 15,339.00 | Total Amount Received |
| event_5170 | image_09 | 723.00 | Total Amount Received |
| event_6033 | image_10 | 79,679.26 | Balance Due |
| event_6859 | image_11 | 3,650.00 | Amount Payable |
| event_7307 | image_12 | 33.50 | Total |
| event_7941 | image_13 | 2,298 | Total paid |
| event_9421 | image_14 | 4,543.00 | TOTAL |
| event_9806 | image_15 | 9,968.00 | Grand Total |
| event_10521 | image_16 | 393.22 | Total |

### Manual visual verification

The source images were opened directly and checked against the cached model results:

- `image_01` / `event_253`: the payslip has gross salary `4,500,000`, subtotal earnings `4,780,800`, deductions `415,800`, and **Net Pay `4,365,000`**. The model selected the payable net amount.
- `image_03` / `event_1545`: the grocery receipt has many line items and **Net Amount/Cash Paid `41,272.00`**. The model selected the final paid amount.
- `image_04` / `event_1700`: the delivered grocery document says **13 items**, shows a **TOTAL ORDER BILL DETAILS** section, and labels the order-level `₹2,854.00` as **Item Bill**. The 13 visible item amounts sum to exactly `₹2,854.00`, so this label is a document-specific total, not a single line-item charge.
- `image_06` / `event_3051`: the invoice has tax columns and line totals but final invoice **Total `1,995.00`**. The model selected the final total.
- `image_07` / `event_3231`: the restaurant receipt has subtotal `8,122.00`, taxes, and final **Total `8,528.10`**. The model selected the tax-inclusive total.
- `image_11` / `event_6859`: the hospital bill has multiple line items/subtotals and **Amount Payable `3,650.00`**. The model selected the payable amount rather than a line item.

No vision result had a currency conflict, and no vision result was auto-applied without a label and high/medium confidence.

### Text — DeepSeek

The DeepSeek endpoint was reached using the supplied `deepseek_api_key`, but it returned **HTTP 402 Payment Required** on the first smoke call. The runner therefore stopped before issuing redundant calls for the other message-bearing users. No text amendment was applied, and the message path remains explicitly unresolved until a funded/usable DeepSeek credential is provided.

This is an external provider limitation, not a silent fallback: the original event ledger is preserved, the sanitized failure is recorded in `evaluation/call_log.jsonl`, and no message is treated as an amendment without a cited extraction result.

## Diff-check evidence

Offline tests independently demonstrate:

- Text proposal without `source_message_id` is rejected with path `text` and the original amount remains unchanged.
- Vision proposal without `source_label` is rejected with path `vision` and the original amount remains unchanged.
- A vision `currency_conflict_flag=true` proposal is rejected and routed to unresolved.
- Low-confidence/null vision proposals remain unresolved.

These are covered in `tests/test_stage5.py` and do not use live providers.

## Forecast regression check

Using `resolved_dataset(...)` and the Stage 4 forecast/Stage 3 engine:

- `request_03` improved from safe amount `0` to `800,894.200` after the payslip net amount was resolved.
- `request_17` changed from `257,777.4916…` to `211,259.48` because the previously missing `₹41,272` grocery purchase raises the protected-grocery daily allowance from `1,601.918333…` to `2,977.651666…` for all 90 forecast days. The cumulative balance impact at the horizon is `90 × (2,977.651666… − 1,601.918333…) = 123,816`; the safe-amount delta is `46,518.011666…` because the before-resolution minimum occurs on `2026-03-14`, while the after-resolution minimum occurs on `2026-05-30`. The minimum date shifts, so the safe-amount comparison is not a one-time debit or a same-date flow comparison.
- `request_20` changed from `33,274.05` to `32,570.00` because the known pending utility debit is now reserved once for `704.05`; its delta is exactly `704.05`.
- Other solved samples did not change in safe amount or earliest date.

These changes are evidence-driven and conservative; no Stage 4 rule was changed.

## Gate status

- [x] Every Stage 4 blank event is resolved through vision; zero remain blank in the resolved ledger.
- [x] Text and vision unjustified-change rejection tests pass separately.
- [x] Six multi-number or ambiguous-label documents were manually checked against source images, including `image_04` / `event_1700`.
- [x] All 16 resolved amounts were type-checked as `Decimal`; comma-grouped values such as `41,272.00` and integer-formatted values such as `2,298` were normalized before parsing.
- [x] Currency-conflict routing is tested and does not apply the amount.
- [x] Vision rerun causes no unexplained sample regression.
- [x] Call log records provider/model/call-site metadata for every live or failed attempt.
- [ ] Text amendment extraction is not complete because the supplied DeepSeek credential returns HTTP 402. Stage 5 must remain open for that external dependency; do not advance to Stage 6 until a usable DeepSeek credential allows the per-user message batch to run.
