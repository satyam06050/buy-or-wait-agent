# Independent manual audit report

The audit was performed against the raw files in `dataset/`, not against the decision-engine internals. `audit/request_47.md` contains the required deep audit. The other cases were independently reconstructed from their request, profile, event, option, message, image, and exchange-rate rows as applicable.

## Audited cases and independent reconstruction

### request_47 — required primary case

The independent result is documented in full in `audit/request_47.md`. The raw supported monthly obligations and protected spending produce a 90-day minimum of IDR 41,489,871.72. The safe request-date amount is IDR 11,440,871.72. Full payment, the supplied installment option, and all permitted stop combinations remain unsafe or ineligible; partial payment is disallowed. The generated row matches on every field.

### request_26 — affordable-now and linked lifecycle case

- Raw profile: IDR 100,845,250 available, IDR 24,768,300 minimum, full payment and installments accepted, maximum five months.
- Request: IDR 15,656,000 on 2025-08-03, completion by 2025-10-07, partial payment disallowed.
- Independent 90-day baseline minimum: IDR 59,267,368.18; capacity is therefore above the requested amount.
- The option rows include a full-payment option on the request date. The 2025-06/07 shopping lifecycle contains a settled reversal (`event_2361`) for a prior charge and a separate settled purchase (`event_2363`); the cancelled authorization (`event_2362`) is not counted as a debit. No pending credit or message creates additional usable income.
- Independent result: full payment on 2025-08-03, no spending change, status `affordable_now`, with the one-payment full-payment plan.

### request_46 — affordable-with-plan installment case

- Raw profile: INR 202,335 available, INR 84,000 minimum; accepted methods are partial payment and installments, maximum seven months.
- Request: INR 49,450 on 2024-12-03, deadline 2025-01-09; partial payment is allowed by the request, but the profile does not accept full payment.
- Independent baseline minimum: approximately INR 157,406.04, so the request-date safe capacity is above the requested amount. The full-payment option is nevertheless not an accepted profile method.
- The supplied option `payment_option_125` is exactly two payments of INR 25,714 on 2024-12-03 and 2024-12-31, total INR 51,428, and is within the maximum installment horizon and deadline. Both payments remain above the minimum in the reconstructed curve.
- Independent result: `affordable_with_plan`, `installments`, exact option-125 schedule, no spending change, and earliest safe full-payment date 2024-12-03.

### request_39 — affordable-later and foreign-currency case

- Raw profile: INR 416,505 available, INR 213,400 minimum; full payment and partial payment accepted; no installment horizon is supplied.
- Request: INR 208,600 on 2026-04-04, deadline 2026-06-15; partial payment is disallowed.
- The user has a monthly settled USD 3,048 payroll history (`event_3492` through `event_3524`) and a scheduled confirmed salary `event_3611` settling on 2026-04-15. The exact dated USD-to-INR rate on that settlement date is 83.33, so the confirmed salary is INR 253,989.84. No inverse, nearest-date, or cross-rate conversion was used.
- Independent baseline minimum before the request is approximately INR 374,091.73, giving request-date safe capacity INR 160,691.73. The full request is not safe on 2026-04-04, but becomes safe on 2026-04-15 after the confirmed salary. That date is before the deadline.
- Independent result: `affordable_later`, `wait`, plan `2026-04-15:208600`, no spending change, earliest full-payment date 2026-04-15.

### request_28 — zero-safe not-affordable case

- Raw profile: EUR 1,789.40 available, EUR 1,100 minimum; only full payment is accepted.
- Request: EUR 1,302.40 on 2024-06-07, partial payment disallowed. The supplied installment options conflict with the profile.
- Independent forecast includes the supported recurring rent, utilities, debt repayment, subscriptions, confirmed regular payroll, and protected transport/grocery allowances. The minimum is approximately EUR -292.96, giving safe capacity zero.
- The payroll message mentions a regular salary and a one-time arrears amount, but it does not justify inventing extra future income beyond the confirmed supported salary treatment; the one-time amount is not used as recurring income.
- Independent result: `not_affordable`, `not_recommended`, no plan, blank earliest date, no spending change.

### request_29 — close-to-request not-affordable case

- Raw profile: ZAR 113,540.10 available, ZAR 28,300 minimum; full payment, partial payment, and installments accepted, maximum five months.
- Request: ZAR 51,524 on 2025-11-04, deadline 2025-11-23; partial payment is disallowed.
- Independent minimum is ZAR 75,893.45, so baseline safe capacity is ZAR 47,593.45, just below the request. The only installment option has 15 payments and exceeds the five-month maximum; no eligible partial schedule remains.
- The payroll message explicitly says the seasonal contract ended and no off-season income or renewal is confirmed, so no future income is added.
- Independent result: `not_affordable`, `not_recommended`, no plan, blank earliest date, no spending change.

### request_30 — spending-change and installment case

- Raw profile: USD 3,752.72 available, USD 900 minimum; partial payment and installments accepted, maximum four months.
- Request: USD 775.20 on 2026-04-06, deadline 2026-06-06; partial payment is disallowed.
- Independent baseline minimum is approximately USD 1,630.91, giving baseline safe capacity USD 730.91. The selected supplied option `payment_option_83` is exactly three payments of USD 268.74 on 2026-04-06, 2026-05-06, and 2026-06-05, total USD 806.22, within the profile horizon and deadline.
- `event_2694` is a same-user USD 35 Family streaming plan, marked `reducible_or_stoppable`; streaming is both reducible and stoppable in the profile, and it is not protected. Stopping it releases cash for the plan without changing the baseline reported safe amount.
- Independent result: `affordable_with_plan`, `installments`, exact option-83 schedule, `stop:event_2694`, and blank earliest date for one safe full payment.

## Field-by-field comparison

| Request | Field | Generated | Independent | Result |
|---|---|---|---|---|
| request_47 | amount_safe_to_pay | 11440871.72 | 11440871.72 | MATCH |
| request_47 | status | not_affordable | not_affordable | MATCH |
| request_47 | method | not_recommended | not_recommended | MATCH |
| request_47 | payment_plan | none | none | MATCH |
| request_47 | earliest_date_for_full_payment | blank | blank | MATCH |
| request_47 | spending_changes_needed | none | none | MATCH |
| request_26 | amount_safe_to_pay | 15656000 | 15656000 | MATCH |
| request_26 | status | affordable_now | affordable_now | MATCH |
| request_26 | method | full_payment | full_payment | MATCH |
| request_26 | payment_plan | 2025-08-03:15656000 | 2025-08-03:15656000 | MATCH |
| request_26 | earliest_date_for_full_payment | 2025-08-03 | 2025-08-03 | MATCH |
| request_26 | spending_changes_needed | none | none | MATCH |
| request_46 | amount_safe_to_pay | 49450 | 49450 | MATCH |
| request_46 | status | affordable_with_plan | affordable_with_plan | MATCH |
| request_46 | method | installments | installments | MATCH |
| request_46 | payment_plan | 2024-12-03:25714\|2024-12-31:25714 | 2024-12-03:25714\|2024-12-31:25714 | MATCH |
| request_46 | earliest_date_for_full_payment | 2024-12-03 | 2024-12-03 | MATCH |
| request_46 | spending_changes_needed | none | none | MATCH |
| request_39 | amount_safe_to_pay | 160691.73 | 160691.73 | MATCH |
| request_39 | status | affordable_later | affordable_later | MATCH |
| request_39 | method | wait | wait | MATCH |
| request_39 | payment_plan | 2026-04-15:208600 | 2026-04-15:208600 | MATCH |
| request_39 | earliest_date_for_full_payment | 2026-04-15 | 2026-04-15 | MATCH |
| request_39 | spending_changes_needed | none | none | MATCH |
| request_28 | amount_safe_to_pay | 0 | 0 | MATCH |
| request_28 | status | not_affordable | not_affordable | MATCH |
| request_28 | method | not_recommended | not_recommended | MATCH |
| request_28 | payment_plan | none | none | MATCH |
| request_28 | earliest_date_for_full_payment | blank | blank | MATCH |
| request_28 | spending_changes_needed | none | none | MATCH |
| request_29 | amount_safe_to_pay | 47593.45 | 47593.45 | MATCH |
| request_29 | status | not_affordable | not_affordable | MATCH |
| request_29 | method | not_recommended | not_recommended | MATCH |
| request_29 | payment_plan | none | none | MATCH |
| request_29 | earliest_date_for_full_payment | blank | blank | MATCH |
| request_29 | spending_changes_needed | none | none | MATCH |
| request_30 | amount_safe_to_pay | 730.91 | 730.91 | MATCH |
| request_30 | status | affordable_with_plan | affordable_with_plan | MATCH |
| request_30 | method | installments | installments | MATCH |
| request_30 | payment_plan | 2026-04-06:268.74\|2026-05-06:268.74\|2026-06-05:268.74 | 2026-04-06:268.74\|2026-05-06:268.74\|2026-06-05:268.74 | MATCH |
| request_30 | earliest_date_for_full_payment | blank | blank | MATCH |
| request_30 | spending_changes_needed | stop:event_2694 | stop:event_2694 | MATCH |

The prose explanations were also checked for consistency with the independently established drivers: rent/recurring obligations for the rejection cases, the supplied option for installment cases, the confirmed salary date for `request_39`, and the permitted streaming stop for `request_30`. No explanation changes a decision field or introduces an unsupported payment amount/date.

## Summary

- **Cases audited:** 7 evaluation requests: `request_47`, `request_26`, `request_46`, `request_39`, `request_28`, `request_29`, and `request_30`.
- **Fields checked:** amount, status, method, payment plan, earliest date, spending changes, supporting explanation consistency, recurring evidence, status handling, profile method restrictions, option schedules, lifecycle rows, foreign-currency conversion, and flexible-event permissions.
- **Field comparisons:** 42 structured field comparisons; all 42 match.
- **Mismatches:** 0.
- **Critical issues:** none found in the audited cases.
- **Non-critical issues:** none affecting correctness. The audited prose is concise and grounded; it is not treated as the source of any calculation.

## Confidence

**PASS**

This conclusion is limited to the independent sample required by `veryfy.md`; it is stronger than a validator-only pass because the selected cases were reconstructed from raw financial evidence and payment options. The primary boundary case, `request_47`, independently reproduces the generated safe amount and rejection, and the remaining cases cover the requested status, method, currency, lifecycle, installment, and spending-change boundaries.
