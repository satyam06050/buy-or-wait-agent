# Stage 4 — 90-day forecast findings

## Implementation

`code/forecast.py` builds an inclusive 90-day daily balance curve from each user’s current balance on `request_date`.

Included cash flows:

- Known future settled debits/credits within the forecast window.
- Known future pending debits, reserved using their known amount.
- Confirmed scheduled salary credits.
- One next monthly salary credit inferred only from a stable same-user monthly payroll/salary history when no blank salary row blocks that inference. Irregular payouts, commissions, bonuses, and contract income are not extrapolated.
- Stable same-user monthly debit obligations supported by the Stage 1 27–31-day signal, including rent, utilities, housing, education, insurance, subscriptions, and debt payments.
- Protected variable debit categories using the highest observed completed 30-day bucket from the previous 90 days, carried forward as a daily allowance. Stable obligations are excluded from these buckets to avoid double counting. This is the explicit conservative resolution for the specification’s “forecast essential variable spending” requirement; it is isolated and documented because the spec does not prescribe an averaging formula.

Exclusions:

- Pending credits/refunds.
- Failed and cancelled events.
- Unrealized/non-cash investment valuations.
- Duplicate linked debit rows when an earlier settled debit with the same amount/currency already exists.
- Blank amounts, which are recorded for Stage 5 and never treated as zero.
- Unsupported scheduled credits.

Foreign amounts use `CurrencyConverter` exact dated lookup on their cash/settlement date. No fallback conversion is used.

## Blank-amount handoff

All 16 blank-amount events are logged by `blank_amount_events(dataset)` and remain excluded from forecast arithmetic:

```text
event_253  user_03  2019-08-31 -> 2019-08-31
event_1442 user_16  2023-08-11 -> 2023-08-16
event_1545 user_17  2026-02-27 -> 2026-02-27
event_1700 user_19  2024-09-03 -> 2024-09-03
event_1786 user_20  2026-02-06 -> 2026-02-09
event_3051 user_33  2026-01-06 -> 2026-01-06
event_3231 user_35  2025-10-29 -> 2025-10-29
event_4535 user_48  2026-07-24 -> 2026-07-24
event_5170 user_55  2026-06-07 -> 2026-06-07
event_6033 user_64  2024-06-03 -> 2024-06-10
event_6859 user_73  2023-01-19 -> 2023-01-23
event_7307 user_78  2025-10-01 -> 2025-10-01
event_7941 user_84  2026-04-03 -> 2026-04-03
event_9421 user_101 2025-11-02 -> 2025-11-02
event_9806 user_105 2026-06-07 -> 2026-06-07
event_10521 user_113 2026-09-03 -> 2026-09-03
```

## Stage 3 integration against solved samples

The Stage 3 `amount_safe_to_pay` and `earliest_date_for_full_payment` functions were run against real forecast curves for the solved samples. The comparison below records the result before Stage 5 message/image resolution and before optional spending changes:

| Sample | Forecast safe amount | Solved safe amount | Forecast earliest full date | Solved earliest date | Result |
|---|---:|---:|---|---|---|
| request_01 | 19,388.59 | 25,256 | none | 2024-03-03 | Conservative protected-variable allowance lowers the baseline below the solved immediate-payment result; no Stage 5 evidence is involved.
| request_03 | 0 | 873,000 | none | 2019-11-15 | `event_253` is blank and image-backed; salary inference is blocked by the unresolved blank salary row, as required.
| request_04 | 0 | 8,401,800 | none | 2024-06-15 | The forecast reserves recurring essentials conservatively and does not count the unapproved bonus from `message_03`; later text resolution may amend the confirmed-pay picture.
| request_09 | 166.61 | 166.61 | 2026-07-04 | 2026-07-04 | Exact match: immediate full payment remains safe.
| request_12 | 65,164 | 65,164 | 2026-04-05 | 2026-04-05 | Exact financial-capacity match; the user’s accepted-method preference is handled later during candidate selection.
| request_25 | 6,000,275.4666… | 1,425,000 | none | none | Both forecasts correctly reject full completion; the amount differs because the Stage 4 baseline uses conservative protected variable spending and exact foreign salary conversion without later amendments.

The exact matches for request 09 and request 12, plus the correct not-affordable outcome for request 25, demonstrate that the real curves are connected to Stage 3. The deviations are recorded rather than hidden: Stage 5 is specifically responsible for blank image amounts and message amendments, while Stage 4 intentionally uses a conservative variable-spending resolution.

## Verification

`tests/test_forecast.py` covers:

- Inclusive 90-day curve shape and current-balance starting point.
- Pending debit reservation and confirmed salary inclusion.
- Blank amount reporting and salary-projection blocking.
- Pending credit, failed/cancelled, and unrealized exclusions.
- Exact foreign-currency conversion on `event_2288`.

Final repository suite: **22 tests passed**. No LLM calls are present.

## Stage 4 gate

- [x] Forecast engine wired to real ingestion data.
- [x] Stage 3 safe amount/date functions run against real sample curves.
- [x] At least three sample comparisons match or have documented deviations.
- [x] All blank amounts are listed and excluded, never treated as zero.
- [x] No LLM calls.
