# Independent audit: request_47

This review uses the raw CSV rows and the rules in `audit/problem_rules.md`. The generated explanation is not used as evidence.

## Request

| Field | Raw value |
|---|---|
| request_id | `request_47` |
| user_id | `user_47` |
| request_date | 2025-05-05 |
| requested_amount | IDR 38,114,000 |
| desired_completion_date | 2025-06-19 |
| allows_partial_payment | false |
| request_text | “What is the most I can put toward this repair right now? I need to decide by 19 June 2025. I've received a repair quote for IDR 38,114,000.” |

## Financial profile

| Field | Raw value |
|---|---|
| home currency | IDR |
| current available balance | IDR 112,924,150 |
| minimum balance to keep | IDR 30,049,000 |
| protected categories | rent, groceries, transport |
| categories user may reduce | dining, entertainment |
| categories user may stop | gym, music_subscription, delivery_membership |
| accepted methods | full_payment, installments |
| max installment months | 10 |

## Relevant raw evidence

There are 114 raw events for `user_47`. No amount is blank for this user, there is no foreign-currency conversion in this case, and there is no linked lifecycle row. The only message is `message_34`, an Indonesian RideGrid notice saying a future app payment is still pending and may change; it has no related event ID and supplies no confirmed credit, so it is excluded from cash flow.

The following settled rows establish the recurring schedules used in the independent forecast. Dates are settlement dates; the request-date balance already includes rows on or before 2025-05-05.

| Evidence rows | Observed cadence and amount | Independent treatment in the 90-day forecast |
|---|---:|---|
| `event_4317`, `event_4327`, `event_4337`, `event_4343` — Shared housing rent | 2025-02-04, 03-04, 04-04, 05-04; IDR 12,065,000 | Supported monthly rent; project 2025-06-04 and 2025-07-04 |
| `event_4318`, `event_4328`, `event_4338` — Household utility payment | 2025-02-08, 03-08, 04-08; latest IDR 2,171,424.17 | Supported monthly utility; project 2025-05-08, 06-08, 07-08 using the latest settled amount |
| `event_4321`, `event_4331`, `event_4341` — Community fitness plan | 12th of month; IDR 1,060,200 | Subscription cadence supported; project 05-12, 06-12, 07-12. It is stoppable and permitted by the profile, but not changed in the baseline |
| `event_4319`, `event_4329`, `event_4339` — Music service subscription | 13th of month; IDR 497,800 | Subscription cadence supported; project 05-13, 06-13, 07-13. It is stoppable and permitted by the profile, but not changed in the baseline |
| `event_4320`, `event_4330`, `event_4340` — Delivery service plan | 15th of month; IDR 390,450 | Subscription cadence supported; project 05-15, 06-15, 07-15. It is stoppable and permitted by the profile, but not changed in the baseline |
| `event_4357`–`event_4368` — groceries | Four settled grocery rows in each of the three preceding 30-day buckets | Protected variable spending is reserved at the highest observed bucket: IDR 6,125,380.92 / 30 = IDR 204,179.364 per day |
| `event_4381`–`event_4393` — transport | Five, then four, then four settled transport rows in the preceding buckets | Protected variable spending is reserved at the highest observed bucket: IDR 5,522,837.67 / 30 = IDR 184,094.589 per day |
| salary/payout rows through `event_4336` | Irregular delivery/task/platform payouts, not regular salary/payroll | Not projected as future income; the RideGrid message is also not a confirmed credit |
| dining and entertainment rows | Flexible/reducible but not protected | Not used as protected baseline allowance; no optional change is assumed for the baseline |

All future projected items above are debits. There are no confirmed future credits for this user. Failed, cancelled, pending-credit, unrealized, and non-cash rows do not add usable cash; none of those rows creates a supported future credit here.

## Baseline forecast

The independent calculation starts with IDR 112,924,150 on 2025-05-05. Every day after the request date reserves IDR 204,179.364 for groceries and IDR 184,094.589 for transport, or IDR 388,273.953 per day, plus the supported recurring rows listed above.

For readability, the following is a chronological checkpoint table. Daily variable reserves are applied on every intervening date; the listed recurring debit is applied on the stated date. Values are rounded to two decimals for display, while the arithmetic retains the raw decimal amounts.

| Date | Cash-flow applied at checkpoint | Independent balance |
|---|---|---:|
| 2025-05-05 | Starting available balance | IDR 112,924,150.00 |
| 2025-05-06 to 2025-05-07 | 2 days of protected variable reserve | IDR 112,147,602.09 |
| 2025-05-08 | Daily reserve plus utility IDR 2,171,424.17 | IDR 109,587,903.97 |
| 2025-05-12 | Daily reserve plus gym IDR 1,060,200 | IDR 106,974,608.16 |
| 2025-05-13 | Daily reserve plus music subscription IDR 497,800 | IDR 106,088,534.21 |
| 2025-05-15 | Daily reserve plus delivery plan IDR 390,450 | IDR 104,921,536.30 |
| 2025-06-04 | Daily reserve plus rent IDR 12,065,000 | IDR 85,091,057.24 |
| 2025-06-08 | Daily reserve plus utility IDR 2,171,424.17 | IDR 81,366,537.26 |
| 2025-07-04 | Daily reserve plus rent IDR 12,065,000 | IDR 57,257,964.48 |
| 2025-07-08 | Daily reserve plus utility IDR 2,171,424.17 | IDR 53,533,444.50 |
| 2025-08-03 | End of 90-day window; daily reserve applied | **IDR 41,489,871.72** |

The independently calculated baseline minimum is IDR 41,489,871.72 on 2025-08-03.

## Full-payment simulation

Subtracting the requested IDR 38,114,000 on 2025-05-05 from every subsequent balance gives a forecast minimum of:

`IDR 41,489,871.72 - IDR 38,114,000 = IDR 3,375,871.72`

That is below the required IDR 30,049,000 minimum. Therefore full payment on the request date is unsafe. The shortfall at the low point is IDR 26,673,128.28.

## Safe amount calculation

The maximum request-date payment before optional changes is the baseline minimum less the required reserve, capped at the requested amount:

```text
IDR 41,489,871.72 - IDR 30,049,000.00 = IDR 11,440,871.72
min(IDR 11,440,871.72, IDR 38,114,000.00) = IDR 11,440,871.72
```

The independent result is therefore **IDR 11,440,871.72**, not zero and not the full request. No date in the 90-day forecast makes a one-time full payment safe through the end of the forecast, so the earliest full-payment date is blank.

Permitted stops can release at most IDR 5,845,350 over the forecast from the three monthly subscriptions (gym, music, and delivery). Even applying that release gives a full-payment low point of only IDR 9,221,221.72, still below the reserve. Reducible dining/entertainment actions do not make the supplied installment schedule safe within the available horizon either.

## Payment-option analysis

Raw options for `request_47`:

| Option | Supplied schedule | Independent result |
|---|---|---|
| `payment_option_127` | Full payment IDR 38,114,000 on 2025-05-05; total IDR 38,114,000 | Unsafe: simulated low point IDR 3,375,871.72, below reserve |
| `payment_option_128` | 15 payments of IDR 2,795,026.67 starting 2025-05-12 every 30 days; total IDR 41,925,400.05 | Not eligible: 15 payments exceed the profile's 10-month maximum; it also runs to 2026-07-06, beyond the 2025-06-19 desired completion date, and the schedule is unsafe against the baseline reserve |

Partial payment is disallowed by the request (`allows_partial_payment=false`) and is not accepted in the profile. No eligible complete plan remains.

## Final independent decision

| Field | Independent result |
|---|---|
| amount_safe_to_pay | IDR 11,440,871.72 |
| affordability_status | `not_affordable` |
| recommended_payment_method | `not_recommended` |
| payment_plan | `none` |
| earliest_date_for_full_payment | blank |
| spending_changes_needed | `none` |

## Comparison with `output.csv`

The generated row is:

```text
request_47,11440871.72,not_affordable,not_recommended,none,,none,Do not make this payment under the available safe plans. The forecast reserves 12065000 for Shared housing rent on 2025-07-04.
```

| Field | Generated | Independent | Result |
|---|---|---|---|
| amount_safe_to_pay | 11,440,871.72 | 11,440,871.72 | MATCH |
| affordability_status | not_affordable | not_affordable | MATCH |
| recommended_payment_method | not_recommended | not_recommended | MATCH |
| payment_plan | none | none | MATCH |
| earliest_date_for_full_payment | blank | blank | MATCH |
| spending_changes_needed | none | none | MATCH |
| decision explanation | Grounded in the projected July rent and no safe complete plan | Same decision drivers; generated prose is not used as calculation evidence | MATCH |

