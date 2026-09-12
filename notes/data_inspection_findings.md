# Stage 1 — Data inspection findings

Inspection scripts:

- `python3 notes/inspect_recurrence.py`
- `python3 notes/inspect_currency_coverage.py`

Both scripts are throwaway inspection tools. They only read CSVs and print evidence; neither is imported by a pipeline or performs a forecast/conversion.

## 1. Recurrence and date intervals

### Dataset-wide measurements

- `financial_events.csv` contains **25,342 rows** and **8,002** distinct `(user_id, category, description)` groups.
- **6,109** groups repeat at least once.
- Across adjacent dates within those repeated groups, the most common deltas are **31 days (4,441)**, **30 days (2,947)**, **28 days (1,271)**, **14 days (1,049)**, **7 days (898)**, and **21 days (726)**. The broader distribution also includes 29, 27, 42, 35, 56, 70, 84, 91, 98, 105, 112, 120, 126, 133, 140, 147, 154, and other irregular gaps.
- Same-day and one-day adjacent rows also occur in repeated label groups, so the existence of a repeated description alone is not enough to call an event recurring.

### Reliable signal found

The reliable recurrence signal for a forecast is a repeated **same-user obligation** with a stable calendar cadence and consistent semantic role—especially rent, salary, subscription, or debt payment—not merely a repeated free-text label. The actual recurring cadence observed for these obligations is **monthly, approximately 28–31 days**. A smaller set of platform-income histories shows roughly weekly observations, commonly 7 days but also 9–17 days; because that cadence is irregular, it is not a reliable future-income recurrence signal without additional confirmation.

Concrete evidence:

1. User 01 apartment rent repeats as `event_01` (2023-10-02), `event_07` (2023-11-02, +31 days), `event_13` (2023-12-02, +30), `event_19` (2024-01-02, +31), `event_26` (2024-02-02, +31), and `event_32` (2024-03-02, +29). This is a stable monthly obligation with the same description/category and fixed amount.
2. User 07 monthly rent `event_559`, `event_564`, `event_569`, `event_574`, and `event_579` occurs on the fourth of successive months from 2024-04-04 through 2024-08-04, with 30/31-day calendar gaps. The same user’s salary rows `event_558`, `event_563`, `event_568`, `event_573`, and `event_578` recur around the 15th; `event_578` has a later settlement date, demonstrating why settlement date matters to cash flow.
3. User 06’s family streaming plan `event_444`, `event_452`, `event_460`, `event_468`, and `event_476` occurs on the 10th of successive months (31, 30, 31, and 30 days). The event is also marked `stoppable`, so recurrence and flexibility are separate properties.
4. Platform-income labels are materially less regular: user 10’s delivery/driver payout groups include 7-, 9-, 16-, and 17-day gaps (`event_791`/`event_799`, `event_821`/`event_829`, `event_831`/`event_839`). These should not be forecast as a fixed weekly salary solely from the description.
5. Variable spending demonstrates why label repetition is insufficient: user 01 grocery/dining/transport descriptions repeat with 7-, 14-, 21-, 28-, 35-, 42-, 56-, and 70-day gaps, rather than one stable schedule. Such expenses need conservative treatment later, not automatic recurring-event extrapolation from the label.

### Linked-event interpretation

There are **58 rows with a nonblank `linked_event_id`**, pointing to **58 unique targets**. These links describe transaction lifecycles, not recurring schedules. The observed pairs include:

- Cancellation/replacement: `event_100` is a cancelled card authorization and `event_101` is the later settled card purchase.
- Settled debit/refund: `event_98` is a settled debit and `event_99` is its settled credit reversal; `event_1784` is a settled debit and `event_1785` is a still-pending refund.
- Failed/retry: `event_12808` is a failed debt payment and `event_12809` is the scheduled retry.
- Investment lifecycle: `event_1855` is a settled investment purchase and `event_1856` is an unrealized non-cash valuation; the link does not make the valuation available cash.

Therefore Stage 2+ must use status/event type and settlement state, not treat `linked_event_id` as evidence of recurrence or as permission to double-count both sides of a lifecycle.

### Stage 1 recurrence conclusion

Use stable, same-user recurring obligations supported by repeated dates and semantic role, with monthly **28–31 day** intervals as the dominant recurring cadence. Treat irregular platform income and variable spending as non-recurring unless a later explicit rule/evidence supports them. No alternative recurrence heuristic is justified by this inspection.

## 2. Currency coverage

The schema defines request amounts as already expressed in each user’s `home_currency`; requests have no separate request-currency field. The conversion audit therefore checks every event whose `currency` differs from that user’s `home_currency`, using the event’s `settlement_date` and exact `(from_currency, to_currency, date)` key.

Results from the full dataset:

- **140 foreign-currency event rows** require conversion.
- **140/140** have an exact exchange-rate row.
- **0 gaps** were found.
- The 140 rows span 101 distinct dated currency keys and these directions: USD→IDR (24 keys), USD→INR (26), USD→EUR (19), EUR→ZAR (16), and EUR→USD (16).

Concrete covered examples:

1. `event_2167` (user 25) is USD 1,800 settling 2023-10-15 for an IDR-home user; the exact key `(2023-10-15, USD, IDR)` exists in `exchange_rates.csv`.
2. `event_15451` (user 159) is a EUR event settling 2023-10-15 for a ZAR-home user; the exact `(2023-10-15, EUR, ZAR)` key exists.
3. `event_21583` (user 235) is a EUR event settling 2024-04-15 for a USD-home user; the exact `(2024-04-15, EUR, USD)` key exists.
4. `event_3492` (user 39) is a USD event settling 2025-11-15 for an INR-home user; the exact `(2025-11-15, USD, INR)` key exists.

### Stage 1 currency conclusion

The real dataset has **no conversion gaps**, so Stage 2 must implement **direct dated lookup only**. No inverse-rate fallback, nearest-date fallback, cross-rate composition, or hypothetical gap handling is justified. Same-currency events need no lookup; foreign events use the exact settlement-date direction from the table.

## 3. Gate status

- [x] The recurrence signal and observed intervals are stated with event/user evidence.
- [x] Linked-event chains are distinguished from recurrence with concrete lifecycle examples.
- [x] Currency coverage is measured on the full dataset: 140 covered, zero gaps.
- [x] Findings are traceable to specific event IDs and users.
