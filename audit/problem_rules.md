# Rules used for the independent audit

Source: `problem_statement.md` and `README.md`. This file intentionally records only rules relevant to the selected-output verification.

## Forecast and safety

- Forecast the 90 days beginning on `request_date` using confirmed cash flows, recurring obligations supported by history, relevant evidence, and fixed dated exchange rates.
- A plan is safe only when every listed payment can be made, protected/essential spending is covered, and balance never falls below `minimum_balance_to_keep` throughout the forecast.
- Ignore pending credits, failed/cancelled transactions, duplicate lifecycle representations, and unrealized/non-cash investment values.
- Blank event amounts must be resolved from the linked image when available; they are never zero.
- Confirmed salary is counted on its settlement date, not before. Do not invent unsupported income, expenses, payment options, or rates.
- Convert foreign-currency records using the exact supplied dated currency-pair rate.
- Resolve conflicts using explicit cancellation/settlement/amendment, then newer same-source evidence, then settled records, then the financially safer interpretation.

## Safe amount and earliest date

- `amount_safe_to_pay` is the maximum request-date payment before optional spending changes, while maintaining all protections through the forecast, capped between zero and `requested_amount`.
- `earliest_date_for_full_payment` is the first date when paying the full request as one payment remains safe through the forecast. It is blank when no such date exists within the forecast.
- This capacity date is independent of payment-method preference.

## Statuses and methods

- `affordable_now`: full payment is safe on `request_date` and the user accepts `full_payment`.
- `affordable_with_plan`: the complete request is safe through a partial schedule, supplied installments, or permitted spending changes.
- `affordable_later`: full payment becomes safe later.
- `not_affordable`: no complete safe request can be recommended within the forecast/deadline constraints.
- Immediate methods (`full_payment`, `partial_payment`, `installments`) are eligible only when accepted in the financial profile.
- `wait` is eligible when full payment becomes safe later and the user accepts full payment.
- `not_recommended` is the fallback when no safe eligible plan exists.

## Payment plans

- Payment entries are chronological `YYYY-MM-DD:amount` values separated by `|`; use `none` when no payment is recommended.
- Installment plans must copy a supplied payment option's dates, amounts, payment count, and total payable amount, and respect the profile's maximum installment horizon and desired completion date.
- Partial payment requires request permission, user acceptance, `0 < amount_safe_to_pay < requested_amount`, and completion by `desired_completion_date`.
- Partial payment has exactly two payments: safe amount on `request_date`, then the remainder on `earliest_date_for_full_payment`.

## Spending changes and explanations

- Only recurring expenses marked flexible/reducible/stoppable in the supplied data and permitted by the profile may be stopped or reduced; no protected expense may be changed.
- At most three changes may be used, and stop/reduce actions cannot both target one event.
- `decision_explanation` must be concise, grounded in the final plan, and consistent with the financial facts; it must not change any decision field.
