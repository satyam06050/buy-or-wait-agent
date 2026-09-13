# Phase 7 — Validator and full-run findings

## Implemented

- `code/validator.py`
  - Typed `OutputRow` representation.
  - Validates exact output columns and request coverage.
  - Enforces `0 <= amount_safe_to_pay <= requested_amount`.
  - Enforces status and payment-method enums.
  - Validates chronological payment-plan syntax.
  - Validates exact two-payment partial plans, including request-date first payment, safe amount, exact sum, and desired completion deadline.
  - Validates installment plans against supplied source option dates, amounts, count, and total payable amount.
  - Enforces `affordable_now` earliest date equal to request date.
  - Enforces wait/full/not-recommended plan relationships.
  - Validates spending-change syntax, maximum of three changes, existing event IDs, flexible-event requirement, non-increasing amounts, and duplicate/conflicting references.
  - Re-parses the written CSV into typed rows and validates the serialized file a second time.
- `code/pipeline.py`
  - Loads the dataset and accepted Stage 5 ledger.
  - Builds 90-day forecasts.
  - Expands supplied installment schedules verbatim.
  - Filters installment options by accepted payment method and `max_installment_months`.
  - Runs the deterministic Stage 3 candidate generator/ranker.
  - Generates explanations only after all decision fields are fixed.
  - Validates before and after writing `output.csv`.
  - Uses atomic CSV replacement.
- `code/main.py`
  - Runnable entry point:
    ```bash
    python3 -m code.main
    ```
  - Explicit development-only offline mode:
    ```bash
    python3 -m code.main --offline-explanations
    ```

## Full dataset run

The explicit offline-explanation validation run processed all **250 evaluation requests** and wrote the required `output.csv` with the exact required column order.

```text
Rows: 250
Serialized output validation: PASS
Validator exceptions: 0
```

Output distribution after the Phase 7 audit corrections:

```text
affordable_now:       34
affordable_with_plan: 29
affordable_later:      4
not_affordable:      183

full_payment:         38
installments:         25
wait:                  4
not_recommended:     183
```

Eight rows now contain permitted spending changes rather than `none` for every request. The actual dataset flexibility values are `reducible`, `stoppable`, and `reducible_or_stoppable`; the search uses those capabilities together with each profile’s permitted categories.

`earliest_date_for_full_payment` is intentionally blank for every `not_affordable` row where no eligible complete plan exists. This removes the prior contradiction seen in `request_75`, `request_102`, and `request_110`: those rows now use permitted spending changes and safe installment plans. All other required output fields are populated.

A fresh-cache run into `/tmp` confirmed the expected call shape:

```text
explanation calls: 250, one per request
text extraction attempts: 1, then fail-fast on provider HTTP 402
```

Stage 5 Gemini results were loaded from cache; no additional image calls were needed.

## Audit corrections

- The decision engine now finds partial-payment dates against the complete forecast suffix, then checks the user’s completion deadline separately. This prevents a deadline-truncated suffix from creating unsafe partial candidates.
- The pipeline keeps `amount_safe_to_pay` from the unmodified baseline curve. Spending changes are searched over all eligible one-to-three-event combinations and only alter plan safety; they never feed back into the safe amount.
- A `not_affordable` row now leaves `earliest_date_for_full_payment` blank, preventing a status/date contradiction when capacity exists but no accepted complete plan is safe. The flagged request IDs are reclassified to accepted installment plans after permitted stop actions.
- All monetary values are quantized to two decimal places before explanation input and CSV serialization. The final output contains no values with more than two fractional digits.
- Supporting facts now name an actual action, forecast driver/commitment, supplied payment option, or permitted spending change. The development-only offline transport therefore produces grounded prose such as “Use the supplied installment schedule… after these permitted changes: stop:event_6960. The forecast reserves … for Shared housing rent…”, rather than exposing a raw forecast minimum.

Real-data candidate audit: partial-payment candidates are generated in the synthetic decision-engine tests, but none of the 80 requests that both allow partial payment and have a suitable accepted profile produced a safe partial schedule across the full 90-day suffix, even after eligible spending-change combinations. The branch is therefore reachable and tested; zero selected partial outputs is a data/forecast result, not an unreachable code path.

## Sample overlap check

`dataset/requests.csv` begins at `request_26`, while solved examples cover `request_01` through `request_25`. There are no overlapping request IDs to diff directly. The shared decision engine, forecast, payment-option handling, and validator were exercised against the solved sample structures in the earlier stage reports.

## Provider limitation

The live default pipeline remains blocked at the explanation step because the supplied DeepSeek credential returns HTTP 402 Payment Required. The normal command fails safely rather than writing explanations that pretend to be LLM-generated. The `--offline-explanations` mode is explicit development validation only and uses a deterministic transport; its call log is written under `/tmp`, not mixed into `evaluation/call_log.jsonl`.

The Stage 7 deterministic validator/full-run gate passes in offline validation. The live LLM full-run gate remains open until a usable DeepSeek credential is available.

## Verification

- **39 tests passed**.
- Python compilation passed.
- Serialized `output.csv` reloaded and passed validation.
- Full row count and required column order verified.
- No API keys or credentials written to output, logs, or source files.
