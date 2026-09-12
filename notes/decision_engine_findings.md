# Stage 3 — Decision engine core findings

## What was built

`code/decision_engine.py` is a standalone pure module. It does not import `ingestion.py`, read CSVs, resolve messages/images, perform recurrence detection, or perform currency conversion.

Implemented primitives:

- `amount_safe_to_pay(baseline_curve, requested_amount, minimum_balance)`
  - Uses the minimum balance in the unmodified baseline curve.
  - Returns `max(0, min(requested_amount, minimum_curve_balance - minimum_balance))`.
  - The result is calculated before any optional spending changes and is passed into later change analysis unchanged.
- `earliest_date_for_full_payment(...)`
  - Checks each candidate date against the minimum suffix balance from that date through the supplied forecast window.
  - Returns the first date whose suffix remains safe after one full payment, or `None`.
- `generate_candidate_plans(...)`
  - Generates full-payment, partial-payment, installment, wait, and not-recommended candidates subject to accepted methods and deadlines.
  - Partial payment is exactly two payments: the frozen safe-now amount on the request date and the remainder on the first safe full-payment date.
  - Installments copy the complete supplied `Payment` schedule and supplied total payable amount verbatim; the engine does not derive dates from frequency/count fields.
- `rank_and_select(candidates)`
  - Filters unsafe candidates and applies only the six specification keys, in order:
    1. complete by deadline;
    2. no spending changes;
    3. lowest total paid;
    4. earliest start;
    5. fewest payments;
    6. lowest `payment_option_id`.
- `spending_changes(frozen_amount_safe_to_pay, changes)`
  - Validates up to three distinct permitted flexible-event changes.
  - Reports released capacity separately while returning the exact frozen safe amount unchanged.

## Synthetic test evidence

`tests/test_decision_engine.py` uses only hand-built date/balance fixtures and no dataset imports. It covers:

- Safe-now amount calculation and request capping.
- Earliest safe full-payment date and no-safe-date behavior.
- `affordable_now`, `affordable_with_plan`, `affordable_later`, and `not_affordable` outcomes.
- Partial-payment rejection when the safe full-payment date is after the desired completion date.
- Verbatim installment payment schedules and supplied total payable amounts.
- Each of the six ranking keys independently; every pair is constructed so removing or reordering that key changes the selected candidate.
- Unsafe-candidate exclusion.
- Spending changes cannot increase or otherwise alter the previously frozen `amount_safe_to_pay`.

## Gate status

- [x] All synthetic decision-engine tests pass.
- [x] Each ranking key has an independent regression test.
- [x] Spending-change immutability is explicitly tested.
- [x] No Stage 3 file imports ingestion or touches a CSV.
- [x] No LLM calls are present.

Final verification: **17 tests passed**, including all Stage 2 ingestion/currency tests.
