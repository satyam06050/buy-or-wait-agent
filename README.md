# HackerRank Orchestrate

Starter repository for the **HackerRank Orchestrate** 24-hour hackathon (September 2026).

## Buy or Wait?

Build an AI-powered financial agent that decides whether a user can safely afford a requested expense.

A user may ask: **"Can I afford this laptop?"**

Answering well takes more than the current balance. The agent must account for recurring expenses, pending payments, essential spending, confirmed income, available payment options, and relevant details buried in messages and images.

For every request, the agent decides whether the user should pay in full, pay partially, use installments, wait, or not proceed. The recommendation must be personalized: two users with the same balance can deserve different answers based on their commitments, priorities, payment preferences, and willingness to adjust flexible expenses.

A recommendation is safe only if the user can complete the full payment plan, cover essential expenses, and stay above their preferred minimum balance throughout the forecast period.

Read [`problem_statement.md`](./problem_statement.md) for the full task spec, input/output schema, allowed values, conflict-resolution rules, and submission format.

---

## Quick Start

Clone the repository and move into the project directory:

```bash
git clone https://github.com/interviewstreet/hackerrank-orchestrate-september26.git
cd hackerrank-orchestrate-september26
```

Build your solution in `code/main.py`, or use another language and document its entry point clearly.

Your solution must:

- Read the input files from `dataset/`
- Generate one prediction for every request
- Write the final predictions to `output.csv` in the repository root

Run the Python entry point from the repository root with:

```bash
python3 -m code.main
```

For a deterministic development validation run that does not contact the explanation provider, use:

```bash
python3 -m code.main --offline-explanations
```

After running your solution, confirm that `output.csv` exists in the repository root and contains the required columns and one row for every request.

## Important File Locations

```text
dataset/        Input data and the blank output template. Do not modify the input data.
code/           Your solution code.
output.csv      Final generated predictions in the repository root.
code.zip        ZIP file containing your complete solution for submission.
```

The blank template at `dataset/output.csv` is provided as a reference. Your final generated file must be the root-level `output.csv`.

---

## Repository Layout

```text
.
├── AGENTS.md                         # Rules for AI coding tools + transcript logging
├── problem_statement.md              # Full challenge statement
├── README.md                         # You are here
├── code/                             # Your solution code
├── output.csv                        # Final generated predictions
└── dataset/
    ├── requests.csv                  # 250 requests to evaluate — predict these
    ├── output.csv                    # Blank submission template
    ├── sample_requests.csv           # 25 solved examples
    ├── financial_profiles.csv        # Balances, minimum balance, priorities, preferences
    ├── financial_events.csv          # Historical, pending, and confirmed transactions
    ├── request_payment_options.csv   # Payment options available per request
    ├── exchange_rates.csv            # Fixed, dated conversion rates
    ├── messages.csv                  # Messages tied to users, requests, or events
    ├── images.csv                    # Payroll letters, statements, bills, receipts
    └── media/
        └── images/
```

Only `dataset/requests.csv` requires predictions. Everything else is context. Join user records with `user_id`, request records with `request_id`, supporting evidence with `related_event_id`, and exchange rates with the rate date and currency pair.

Amounts are in the user's `home_currency` — the dataset uses INR, ZAR, IDR, USD, and EUR, and every conversion rate you need is in `exchange_rates.csv`. All dates are `YYYY-MM-DD`. Live exchange rates, market data, and banking access are not required.

---

## What You Need to Build

For every row in `dataset/requests.csv`, produce one row in `output.csv` with:

| Column | Meaning |
|---|---|
| `request_id` | The request being answered |
| `amount_safe_to_pay` | Largest amount safe to pay on `request_date` before optional spending changes, after protecting essentials and the minimum balance |
| `affordability_status` | `affordable_now`, `affordable_with_plan`, `affordable_later`, or `not_affordable` |
| `recommended_payment_method` | `full_payment`, `partial_payment`, `installments`, `wait`, or `not_recommended` |
| `payment_plan` | Chronological `<YYYY-MM-DD>:<amount>` entries joined by `\|`, or `none` |
| `earliest_date_for_full_payment` | Earliest date the full amount is forecast safe as one payment; empty if never within the forecast |
| `spending_changes_needed` | Up to three `stop:<event_id>` / `reduce_to:<event_id>:<amount>` changes joined by `\|`, or `none` |
| `decision_explanation` | Short explanation and the financial facts behind it |

`0 <= amount_safe_to_pay <= requested_amount` must always hold. Installment plans must exactly match a supplied payment option, and only recurring expenses marked flexible may be changed.

`affordable_with_plan` means the full request is completed through a partial-payment schedule, installments, or permitted spending changes. Recommend `partial_payment` only when the request allows it, the user accepts it, `0 < amount_safe_to_pay < requested_amount`, and `earliest_date_for_full_payment` is on or before `desired_completion_date`. Use exactly two payments: pay `amount_safe_to_pay` on `request_date`, then pay the remaining amount on `earliest_date_for_full_payment`. The two payments must add up to `requested_amount`. Unlike installments, partial payment does not need to match a supplied payment option.

---

## Suggested Workflow

1. Inspect `dataset/sample_requests.csv` — 25 requests with completed output columns — to understand the expected format and decision style.
2. Reconstruct each user's financial state from `financial_profiles.csv` and `financial_events.csv`: separate recurring expenses from one-time events, reserve pending transactions, count confirmed salary only on its settlement date, and de-duplicate repeated representations of the same event.
3. When an event has a blank `amount`, find its `event_id` as `related_event_id` in `images.csv` and extract the amount from the linked image. Never treat a blank amount as zero. Pull in any other relevant messages, images, and payment options for the request.
4. Forecast forward and generate a plan that keeps the balance above the minimum at every step.
5. Verify deterministically — bounds, plan feasibility, schedule match, flexible-only spending changes — before writing `output.csv`.
6. Score yourself on the solved samples, then run the full dataset.

You may use any language or runtime. Python, JavaScript, and TypeScript are all reasonable choices.

---

## Deterministic forecast findings

### Recurrence

The implementation does not treat repeated descriptions as automatically recurring. Stage 1 found **25,342** financial-event rows, **6,109** repeated groups, and common adjacent intervals of **31 days (4,441)**, **30 days (2,947)**, **28 days (1,271)**, **14 days (1,049)**, **7 days (898)**, and **21 days (726)**. The reliable forecast signal is a repeated same-user obligation with a stable calendar cadence and semantic role; the supported monthly rule is a **28–31 day** cadence.

The finding is traceable to these examples from `notes/data_inspection_findings.md`:

- User 01 apartment rent: `event_01`, `event_07`, `event_13`, `event_19`, `event_26`, and `event_32`, with 29–31 day gaps and a stable amount.
- User 07 monthly rent: `event_559`, `event_564`, `event_569`, `event_574`, and `event_579`, recurring on the fourth of successive months; the same user's salary rows include `event_578`, whose later settlement date demonstrates why settlement date controls cash flow.
- User 06 family streaming: `event_444`, `event_452`, `event_460`, `event_468`, and `event_476`, recurring on the tenth and separately marked `stoppable`.

Platform income is deliberately not projected from a repeated label alone: user 10 payout groups include 7-, 9-, 16-, and 17-day gaps in `event_791`/`event_799`, `event_821`/`event_829`, and `event_831`/`event_839`. Variable spending is reserved conservatively rather than extrapolated as a fixed recurrence.

Linked events are treated as transaction lifecycles, not recurrence. For example, `event_100`/`event_101` is a cancelled authorization followed by a settled purchase, `event_98`/`event_99` is a debit and reversal, and `event_1855`/`event_1856` is a cash investment purchase followed by an unrealized non-cash valuation.

### Currency conversion

The full-dataset inspection found **140 foreign-currency event rows**, with **140/140 exact dated exchange-rate matches** and **zero gaps**. Conversion is therefore a direct lookup using `(settlement_date, from_currency, to_currency)`; the implementation does not use inverse rates, nearest dates, or cross-rate composition. Requests are already expressed in the user's home currency.

Cited coverage examples from `notes/data_inspection_findings.md`:

- `event_2167` (user 25), USD 1,800 settling 2023-10-15 for an IDR-home user, has an exact `(2023-10-15, USD, IDR)` row.
- `event_15451` (user 159), a EUR event settling 2023-10-15 for a ZAR-home user, has an exact `(2023-10-15, EUR, ZAR)` row.
- `event_21583` (user 235), a EUR event settling 2024-04-15 for a USD-home user, has an exact `(2024-04-15, EUR, USD)` row.
- `event_3492` (user 39), a USD event settling 2025-11-15 for an INR-home user, has an exact `(2025-11-15, USD, INR)` row.

## Evidence limitations and conservative handling

Stage 0 recorded image ambiguities such as `event_1442`/`image_02` (total, received, and balance-due fields) and `event_1700`/`image_04` (an item bill whose visible total required manual verification). Stage 5 resolved all 16 previously blank image amounts with the Gemini vision path, and `event_1700` was manually checked against the displayed grocery line items. Text amendment extraction remains explicitly unresolved because the supplied DeepSeek credential returned HTTP 402 Payment Required; no message amendment is silently applied without a cited extraction result. The offline explanation mode is development-only and is not presented as live model usage.

## Re-running, testing, and packaging

From the repository root:

```bash
# deterministic full validation and output generation
python3 -m code.main --offline-explanations

# test suite
python3 -m unittest discover -s tests -v

# package the runnable code, README, and required root evaluation report
package_root=$(pwd)
package_dir=/tmp/buy-or-wait-package
rm -rf "$package_dir"
mkdir -p "$package_dir/evaluation"
cp -a code "$package_dir/code"
cp README.md "$package_dir/README.md"
cp code/evaluation/usage_report.md "$package_dir/evaluation/usage_report.md"
find "$package_dir" -type d -name __pycache__ -prune -exec rm -rf {} +
find "$package_dir" -type f \( -name '*.pyc' -o -name '.env' -o -name '*.jsonl' \) -delete
rm -f "$package_root/code.zip"
(cd "$package_dir" && zip -qr "$package_root/code.zip" .)
unzip -l "$package_root/code.zip"
```

The live command (`python3 -m code.main`) reads provider credentials from environment variables or a local `.env` file and may require funded provider accounts. Never include `.env`, credentials, cached raw evidence, or provider prompts in `code.zip`. Submit `code.zip`, the root `output.csv`, and the root `log.txt` as the chat transcript according to the contest instructions. The package contains `evaluation/usage_report.md`.

## Requirements

Your solution must:

- be runnable from the terminal
- read the provided files from `dataset/`
- produce a valid `output.csv` with the exact required columns in the exact required order
- include one prediction for every `request_id` in `dataset/requests.csv`
- not use organizer-only files or hardcoded labels
- keep behavior deterministic where possible

If you use API keys or secrets, read them from environment variables. Never hardcode secrets in the repo.

---

## Evaluation

Your `output.csv` will be compared against hidden ground-truth values.

The scoring will consider:

- accuracy of `amount_safe_to_pay`
- correctness of `affordability_status`
- correctness of `recommended_payment_method` and `payment_plan`
- accuracy of `earliest_date_for_full_payment`
- validity of `spending_changes_needed`
- usefulness and consistency of `decision_explanation`

### Token Usage And Cost Analysis

Your `code.zip` must include one token-usage file:

```text
evaluation/usage_report.md
```

The report must cover model providers and names, model calls, input and output tokens, total and average tokens per request, estimated total and per-request cost. The reported values must correspond to the final full-dataset run that produced your `output.csv`.

---

## Chat Transcript Logging

This repo includes an [`AGENTS.md`](./AGENTS.md) file for AI coding tools. It asks compatible tools to append conversation summaries to a `log.txt` in the repository root — the same directory as `AGENTS.md`:

| Platform | Path |
|---|---|
| macOS / Linux | `<repo root>/log.txt` |
| Windows | `<repo root>\log.txt` |

The path resolves relative to `AGENTS.md`, so it stays correct across clones, renames, and checkouts. `log.txt` is gitignored — upload it as your chat transcript at submission time. Do not paste secrets into the chat.

In case, the harness you are using is not in the repo root, you can explicitly ask the agent to look for the AGENTS.md in this folder & then continue.

---

## Submission

Submit the following files as instructed by HackerRank:

| File | Description |
|---|---|
| `code.zip` | Full runnable solution, prompts/configuration, README, and the required `evaluation/` folder |
| `output.csv` | Predictions for every row in `dataset/requests.csv` |
| `chat_transcript` | The `log.txt` described above, showing how you developed or used the system |

Before submitting, confirm:

- `output.csv` has one row per row in `dataset/requests.csv` (250 rows plus the header).
- `output.csv` has the exact required columns in the exact required order.
- Every `amount_safe_to_pay` satisfies `0 <= amount_safe_to_pay <= requested_amount`.
- Every installment plan matches a supplied payment option, and every spending change targets a flexible recurring expense.
- Your runnable code, setup instructions, and `evaluation/` folder are included in `code.zip`.
