# Independent Manual Audit — Buy or Wait

You are an independent senior financial-systems auditor.

Your job is NOT to modify the implementation.
Your job is to manually reconstruct selected decisions from the raw dataset and determine whether output.csv is correct.

IMPORTANT:
- Do NOT trust the existing decision engine.
- Do NOT trust the existing forecast.py / decision_engine.py calculations.
- Do NOT use the generated output explanation as evidence.
- Do NOT change any source code.
- Do NOT "fix" discrepancies.
- Trace every conclusion back to raw CSV data.
- Use Python only as a calculation/helper tool; the reasoning must be independently reconstructed from the source data.

## Goal

Audit the generated:

    output.csv

against:

    dataset/requests.csv
    dataset/financial_profiles.csv
    dataset/financial_events.csv
    dataset/request_payment_options.csv
    dataset/exchange_rates.csv
    dataset/messages.csv
    dataset/images.csv
    dataset/media/images/

and determine whether the financial decisions are actually correct.

## First: inspect the problem specification

Read:

    problem_statement.md
    README.md

Extract the exact rules for:

- amount_safe_to_pay
- affordability_status
- recommended_payment_method
- payment_plan
- earliest_date_for_full_payment
- spending_changes_needed
- 90-day forecast
- protected expenses
- minimum balance
- partial payment
- installments
- wait
- flexible spending changes

Do NOT invent rules.

Create:

    audit/problem_rules.md

containing only the rules relevant to verification.

---

# Step 1 — Select audit cases

Do NOT audit all 250 rows initially.

Select at least these cases from output.csv:

1. request_47
   - not_affordable
   - safe amount > 0

2. One affordable_now case
   - e.g. request_26

3. One affordable_with_plan case
   - e.g. request_46

4. One affordable_later case
   - e.g. request_39

5. One not_affordable case with safe amount = 0
   - e.g. request_28

6. One not_affordable case where safe amount is close to requested amount
   - choose an appropriate example from the dataset

7. One spending-change case
   - e.g. request_30 or request_34

8. One installment case with multiple payments

9. One case involving foreign currency, if available

10. One case involving linked_event_id / transaction lifecycle, if available

Prefer boundary cases over random cases.

---

# Step 2 — Reconstruct each user independently

For every selected request:

1. Read the request row.
2. Read the user's financial profile.
3. Collect ALL relevant financial events for that user.
4. Sort events by settlement_date.
5. Inspect status, direction, event_type, flexibility, linked_event_id, amount and currency.
6. Resolve blank amounts only using the actual permitted evidence.
7. Inspect relevant messages.
8. Inspect linked images when required.
9. Convert foreign currencies using the exact documented exchange-rate rule.
10. Identify recurring obligations only when supported by actual dataset evidence.

Do NOT call repeated descriptions automatically recurring.

---

# Step 3 — Manually reconstruct the baseline forecast

For each selected request, create a chronological cash-flow table:

date | event_id | description | direction | amount | currency | home-currency amount | balance

Start from the user's available balance.

Apply confirmed cash flows chronologically.

For every future event, explicitly record why it is included or excluded.

Pay special attention to:

- settlement_date
- status
- cancelled events
- failed events
- pending events
- linked lifecycle events
- recurring expenses
- confirmed income
- variable spending
- investments
- unrealized valuations
- blank amounts

Calculate:

    baseline_minimum_balance

independently.

Compare this against the generated output only AFTER completing the independent calculation.

---

# Step 4 — Verify amount_safe_to_pay

For every selected case, independently determine the maximum safe amount.

Do NOT simply copy:

    output.csv.amount_safe_to_pay

Test the request-date payment against the complete forecast.

Determine:

    maximum amount that can be paid on request_date
    while maintaining all required protections

Check the exact problem specification for whether this calculation is before optional spending changes.

For request_47 specifically:

1. Find the exact requested amount.
2. Find the user's current available balance.
3. Find minimum balance to keep.
4. Reconstruct all future confirmed cash flows.
5. Calculate the baseline forecast.
6. Calculate the forecast after paying the full request.
7. Calculate the maximum safe request-date payment independently.
8. Compare that value against:

    11440871.72

Do not assume the existing value is correct.

---

# Step 5 — Verify the status

Independently determine whether the correct status is:

    affordable_now
    affordable_with_plan
    affordable_later
    not_affordable

Do not derive status from the existing output.

Explain exactly why the selected status follows the specification.

---

# Step 6 — Verify payment methods

For each case, inspect the user's allowed payment methods.

Then inspect request_payment_options.csv.

For installment plans:

- use ONLY supplied installment options
- verify every payment date
- verify every payment amount
- verify number of payments
- verify total payable amount
- verify maximum installment-month restriction
- verify completion deadline
- verify balance after every payment

For partial payment:

- verify request allows partial payment
- verify user accepts partial payment
- verify safe amount is strictly between 0 and requested amount
- verify exactly two payments
- verify first payment occurs on request date
- verify remainder is paid on earliest valid full-payment date
- verify desired completion deadline

---

# Step 7 — Verify spending changes

For every row with spending_changes_needed != none:

1. Locate the exact event IDs.
2. Verify they belong to the correct user.
3. Verify they are flexible.
4. Verify the proposed reduction/stop is permitted by the profile.
5. Verify no protected expense was changed.
6. Verify no more than 3 changes.
7. Independently recalculate the resulting forecast.
8. Verify the decision actually becomes feasible because of those changes.

Also verify that amount_safe_to_pay was calculated BEFORE optional spending changes if required by the specification.

---

# Step 8 — Verify request_47 deeply

This is the primary investigation.

Produce a dedicated file:

    audit/request_47.md

Include:

## Request

- request_id
- user_id
- request_date
- requested_amount
- desired_completion_date
- allows_partial_payment
- request_text

## Financial profile

- home currency
- available balance
- minimum balance
- protected categories
- reducible categories
- stoppable categories
- allowed payment methods
- max installment months

## Relevant events

A complete table of every event affecting the 90-day decision.

## Baseline forecast

Show the chronological balance calculation.

## Full-payment simulation

Show the balance impact of paying the full request.

## Safe amount calculation

Independently derive the maximum safe amount.

## Payment-option analysis

Check every supplied payment option.

## Final independent decision

State:

- independently calculated safe amount
- independently calculated status
- independently calculated payment method
- independently calculated payment plan
- independently calculated earliest full-payment date
- independently calculated spending changes

## Comparison

Compare against output.csv.

For every field:

    MATCH
    MISMATCH

If there is a mismatch, explain exactly why.

---

# Step 9 — Audit report

Create:

    audit/final_audit_report.md

Use this format:

| Request | Field | Generated | Independent | Result |
|---|---|---|---|---|
| request_47 | amount_safe_to_pay | ... | ... | MATCH/MISMATCH |
| request_47 | status | ... | ... | MATCH/MISMATCH |
| ... | ... | ... | ... | ... |

Then provide:

## Summary

- cases audited
- fields checked
- matches
- mismatches
- critical issues
- non-critical issues

## Confidence

Classify the implementation as:

    PASS
    PASS WITH WARNINGS
    FAIL

Do not give PASS merely because validators pass.

A validator only proves structural correctness, not financial correctness.

---

# CRITICAL RESTRICTIONS

DO NOT:

- modify code
- modify output.csv
- modify dataset files
- regenerate decisions
- use the existing forecast implementation as the source of truth
- assume the current output is correct
- fix discrepancies silently
- skip request_47
- treat blank amounts as zero
- infer recurring events merely from repeated descriptions

If you discover a discrepancy, STOP and document it.

Only after the audit report is complete should you recommend what code needs to be changed.

The purpose of this task is independent verification, not implementation.