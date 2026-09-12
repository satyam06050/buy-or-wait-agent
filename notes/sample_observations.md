# Stage 0 — Sample observations

This report covers every row in `dataset/sample_requests.csv`. Event IDs, profile values, messages, images, and payment-option IDs below are all from the participant-facing dataset. The observations describe what the supplied solved output implies; they are not labels to copy into the evaluation run.

## Observations

### request_01 / user_01
- **Inputs seen:** ZAR 58,481.10 available, ZAR 18,000 minimum, only `full_payment` accepted. Near the request are settled rent `event_32`, a pending transport debit `event_102` for ZAR 567.60, and scheduled salary `event_103` for ZAR 23,320 on 2024-03-15. `payment_option_01` is the exact no-fee full-payment option.
- **Output given:** Safe amount ZAR 25,256; `affordable_now`; `full_payment`; `2024-03-03:25256`; no changes.
- **Rule implied:** The full request is safe on the request date when the projected 90-day balance, including the pending debit and protected recurring expenses, stays above the minimum and the method is accepted. Do not needlessly use an installment option when full payment is accepted and costs less.

### request_02 / user_02
- **Inputs seen:** IDR 60,383,889.20 available and IDR 29,158,400 minimum. A pending merchant debit `event_185` must be reserved. `message_01` confirms a salary change effective 2025-08-15; it is not an immediately available credit. The user accepts installments and `payment_option_05` is a three-payment schedule of IDR 15,952,906.67 on 2025-08-08, 2025-09-07, and 2025-10-07.
- **Output given:** Safe-now amount IDR 17,229,139.20; `affordable_with_plan`; installments using option 05; earliest single full payment 2025-09-15; no changes.
- **Rule implied:** An exact supplied installment schedule can be safe even when a full payment is not safe today. The output must copy the option’s dates/amounts and respect the user’s installment horizon.

### request_03 / user_03
- **Inputs seen:** IDR 5,810,300 available, IDR 2,668,700 minimum. `event_253` is a blank-amount settled salary row; `image_01` shows a payslip net pay of IDR 4,365,000. `event_254` is a pending pharmacy debit. `message_02` confirms the next payroll but also says a one-time adjustment is separate. The user accepts full payment, partial payment, and installments.
- **Output given:** Safe-now amount IDR 873,000; `affordable_later`; `wait`; full payment on 2019-11-15; no changes.
- **Rule implied:** A blank amount must be extracted from its linked image, and pending debits remain reserved. A future confirmed salary can make the request affordable later, but the current balance cannot be treated as if that salary were already received.

### request_04 / user_04
- **Inputs seen:** IDR 52,206,950 available and IDR 30,686,600 minimum. Settled rent `event_291`, groceries `event_317`, transport `event_343`, and scheduled school fee `event_357` are close to the request date. `message_03` explicitly says the quarterly bonus amount and date are not approved. Only full payment is accepted.
- **Output given:** Safe-now amount IDR 8,401,800; `affordable_later`; `wait`; IDR 12,693,000 on 2024-06-15; no changes.
- **Rule implied:** Do not count an unapproved bonus merely because a message mentions it. Wait for a supported confirmed inflow and protect the minimum plus essential commitments.

### request_05 / user_05
- **Inputs seen:** ZAR 46,475.10 available and ZAR 13,100 minimum. Rent `event_398` and groceries `event_424` are settled; failed utility debit `event_438` must not be treated as a successful cash expense. No acceptable payment option completes the requested ZAR 15,488 safely.
- **Output given:** Safe-now amount ZAR 737; `not_affordable`; `not_recommended`; no plan.
- **Rule implied:** A positive amount safe today does not make the full request affordable. Failed events are excluded, but the request is still rejected when no accepted plan completes it within the forecast.

### request_06 / user_06
- **Inputs seen:** EUR 1,942.40 available and EUR 800 minimum. `message_04` confirms temporarily reduced pay of EUR 1,037.52. `event_476` is a stoppable EUR 19 streaming charge. Full payment is accepted and `payment_option_16` is the no-fee EUR 620.40 option.
- **Output given:** Safe-now amount EUR 603.30; `affordable_with_plan`; full payment today; spending change `stop:event_476`.
- **Rule implied:** Spending changes can make an accepted full-payment plan feasible, but `amount_safe_to_pay` is measured before optional changes and therefore remains EUR 603.30 rather than being recomputed after stopping the subscription.

### request_07 / user_07
- **Inputs seen:** INR 218,945.56 available and INR 93,000 minimum. Rent `event_583` is settled near the request. `message_05` moves the confirmed salary date to 2024-09-23 and says it replaces the earlier date. The user accepts installments only; `payment_option_19` is three INR 68,432 payments on 2024-09-12, 2024-10-10, and 2024-11-07.
- **Output given:** Safe-now amount INR 87,170.56; `affordable_with_plan`; exact option-19 installments; earliest full-payment date 2024-10-23; no changes.
- **Rule implied:** A newer same-source date amendment controls the forecast. Earliest financial capacity is reported independently from the selected installment preference.

### request_08 / user_08
- **Inputs seen:** EUR 1,536.57 available and EUR 800 minimum. Recent rent `event_650`, groceries `event_677`, utilities `event_651`, and transport `event_703` are protected/essential. `message_06` confirms the next salary is reduced to EUR 1,422.85. Only full payment is accepted.
- **Output given:** Safe-now amount EUR 284.57; `affordable_later`; wait; full payment on 2025-04-15; no changes.
- **Rule implied:** A confirmed but reduced future salary is usable on its settlement date, not before. If the full request becomes safe only later, use `wait` rather than an ineligible installment.

### request_09 / user_09
- **Inputs seen:** EUR 2,231.10 available and EUR 600 minimum. Recent groceries `event_770`, dining `event_788`, and rent `event_752` are visible. Full payment is accepted and `payment_option_24` is the no-fee EUR 166.61 option.
- **Output given:** Safe amount equals the full EUR 166.61; `affordable_now`; full payment today; no changes.
- **Rule implied:** A small full request is immediately affordable when the projected minimum remains protected; no spending change is needed merely because flexible methods exist.

### request_10 / user_10
- **Inputs seen:** INR 750,155 available and INR 225,400 minimum. Rent `event_840` and groceries `event_866` are close to the request. `message_07` says the next QuickCrew payout is pending, variable, and not withdrawable until completed. The user accepts partial payment and installments, but neither supplied option safely completes INR 266,700.
- **Output given:** Safe-now amount INR 12,700; `not_affordable`; `not_recommended`; no plan.
- **Rule implied:** Pending/variable platform earnings are not confirmed income. A request can be rejected even with a large current balance when the 90-day commitments and minimum make every complete plan unsafe.

### request_11 / user_11
- **Inputs seen:** IDR 63,531,795 available and IDR 34,140,600 minimum. `event_989` is a reducible dining expense with minimum allowed amount IDR 665,950. `message_08` confirms base salary IDR 38,760,000 but says unsettled commission is not payable. Full payment is accepted and `payment_option_29` is no-fee full payment.
- **Output given:** Safe-now amount IDR 12,510,645; `affordable_with_plan`; full payment today; `reduce_to:event_989:665950`.
- **Rule implied:** A permitted flexible expense can be reduced to its stated minimum to make the full request feasible. The output’s safe-now amount remains the pre-change amount, while the selected payment plan can be full payment after the explicitly listed change.

### request_12 / user_12
- **Inputs seen:** ZAR 193,089.89 available and ZAR 43,200 minimum. Monthly rent `event_1018` is settled. `message_09` says the seasonal contract ended and no off-season income or renewal is confirmed. The only suitable option is `payment_option_33`: three ZAR 22,590.19 payments beginning 2026-04-19.
- **Output given:** Safe amount equals the full ZAR 65,164; `affordable_with_plan`; exact option-33 installments; earliest full-payment date is the request date; no changes.
- **Rule implied:** A request may be financially safe as a single payment while `full_payment` is not the user’s accepted method. The status then reflects the chosen installment plan, not a lack of capacity.

### request_13 / user_13
- **Inputs seen:** EUR 2,789.52 available and EUR 1,300 minimum. Rent `event_1094`, utilities `event_1095`, groceries `event_1121`, and transport `event_1147` are recent. `event_1161` is a scheduled next confirmed salary; the history supports recurring salary dates. Only full payment is accepted.
- **Output given:** Safe-now amount EUR 433.40; `affordable_later`; wait; full payment on 2024-05-15; no changes.
- **Rule implied:** Essential recurring spending can push the first safe full-payment date beyond the next single credit; forecast the full horizon rather than comparing only current balance with request amount.

### request_14 / user_14
- **Inputs seen:** EUR 3,931.74 available and EUR 2,200 minimum. Rent `event_1200` and groceries `event_1226` are recent. `message_10` confirms salary resumes on 2025-08-15 but also says a recurring childcare payment begins in that month. The user accepts only partial payment and no partial schedule can complete EUR 5,414.20 safely.
- **Output given:** Safe-now amount EUR 597.74; `not_affordable`; `not_recommended`; no plan.
- **Rule implied:** Messages can amend future commitments as well as income. Do not assume salary resumption alone makes a large request affordable when a new recurring protected/fixed commitment begins at the same time.

### request_15 / user_15
- **Inputs seen:** EUR 1,770.05 available and EUR 1,200 minimum. Rent `event_1272` is settled on 2026-01-04. `message_11` confirms first salary EUR 1,661 on 2026-01-15, after the request date. Only partial payment is accepted and the installment offers carry extra cost.
- **Output given:** Safe-now amount EUR 83.05; `not_affordable`; `not_recommended`; no plan.
- **Rule implied:** A confirmed future salary is not available today, and an accepted-method constraint can rule out otherwise possible full-payment or installment candidates.

### request_16 / user_16
- **Inputs seen:** INR 362,370 available and INR 122,400 minimum. Recent rent, utilities, debt, groceries, and transport are settled. `event_1442` is a scheduled blank-amount outstanding rent row linked to `image_02`; the image shows total received INR 200,000, amount received INR 100,000, and balance due INR 100,000. `message_12` says the renewed lease increases monthly rent by 12%.
- **Output given:** Safe amount INR 122,500; `affordable_now`; full payment today; no changes.
- **Rule implied:** Blank amounts require image extraction and the payable/balance-due field must be distinguished from document totals and already-paid amounts. The output still has to reserve the scheduled liability.

### request_17 / user_17
- **Inputs seen:** INR 550,379.58 available and INR 166,100 minimum. Blank settled grocery event `event_1545` is linked to `image_03`, whose net amount is INR 41,272. `event_1544` is a settled reimbursement linked to an earlier expense. `event_1546` is scheduled salary on 2026-03-15. `payment_option_47` is the exact three-payment plan.
- **Output given:** Safe amount INR 243,849.58; `affordable_with_plan`; option-47 installments; earliest full-payment date 2026-03-15; no changes.
- **Rule implied:** Use the image’s net/payable amount, not a line-item or subtotal, and treat a settled credit as available on settlement. A supplied installment plan can be selected when it preserves the minimum through the salary date.

### request_18 / user_18
- **Inputs seen:** EUR 2,486 available and EUR 1,400 minimum. Recent groceries `event_1595`, housing `event_1577`, and dining `event_1621` are visible. `message_13` says a matching debit and credit are a transfer between the user’s own accounts, not new income. The user accepts full or partial payment; full payment becomes safe later.
- **Output given:** Safe-now amount EUR 462; `affordable_later`; wait; full payment on 2026-09-15; no changes.
- **Rule implied:** Do not create spendable income from an internal transfer or matching ledger entries. When full payment is later safe and accepted, `wait` is preferred over unsafe immediate payment.

### request_19 / user_19
- **Inputs seen:** INR 199,545 available and INR 92,800 minimum. `event_1700` is a blank settled delivered-grocery event linked to cropped `image_04`; the visible image shows an item bill of INR 2,854 but not the final payable section. The user accepts partial payment; `payment_option_52` is full payment and the other options add fees.
- **Output given:** Safe-now amount INR 28,820; `affordable_with_plan`; partial payment INR 28,820 on 2024-09-04 and INR 10,840 on 2024-09-15; no changes.
- **Rule implied:** Partial payment is eligible only when explicitly allowed, accepted, strictly between zero and the request total, and completed by the desired date. It uses exactly two payments and need not match a supplied installment option.

### request_20 / user_20
- **Inputs seen:** INR 102,609.05 available and INR 64,500 minimum. Settled housing/utilities are present, pending debit `event_1787` must be reserved, and pending refund `event_1785` is linked to settled expense `event_1784`; `message_14` confirms the refund has not arrived. Blank pending telecom event `event_1786` is linked to `image_05`, which shows current total INR 704.05 and a later amount INR 822.05 after the due date.
- **Output given:** Safe-now amount INR 5,400; `not_affordable`; `not_recommended`; no plan.
- **Rule implied:** Pending credits/refunds do not increase available cash before settlement, and pending debits must be reserved. For a bill image, use the amount currently due for the relevant date, not a late amount, and do not let the small safe-now amount imply full affordability.

### request_21 / user_21
- **Inputs seen:** USD 3,911.35 available and USD 1,800 minimum. Rent `event_1818` and pending fuel `event_1857` are near the request; scheduled salary `event_1858` is on 2026-04-15. Unrealized portfolio value `event_1856` is non-cash. `event_1815` is stoppable cloud storage and `event_1816` is reducible streaming with minimum USD 23.50.
- **Output given:** Safe-now amount USD 1,543.35; `affordable_with_plan`; full payment today; `stop:event_1815|reduce_to:event_1816:23.50`.
- **Rule implied:** An unrealized investment valuation is excluded from cash. Multiple permitted changes may be combined on different events, and the selected plan can be full payment today after those changes without changing the pre-change safe amount.

### request_22 / user_22
- **Inputs seen:** EUR 1,132.46 available and EUR 500 minimum. Pending merchant debit `event_1961` must be reserved; unrealized valuation `event_1960` is explicitly described by `message_15` as not sold and not cash. The user accepts installments and `payment_option_61` exactly schedules three EUR 253.59 payments.
- **Output given:** Safe-now amount EUR 475.46; `affordable_with_plan`; option-61 installments; earliest full-payment date 2025-01-15; no changes.
- **Rule implied:** Supporting messages can reinforce that a linked non-cash value must not be counted. Installment totals/dates are taken verbatim and may be safer than the no-fee full option when the user does not accept full payment.

### request_23 / user_23
- **Inputs seen:** ZAR 51,957.90 available and ZAR 27,000 minimum. Rent `event_2002` is settled; pharmacy debit `event_2042` is pending. `message_16` says prize proceeds are still processing and not credited. Full payment is accepted, and `payment_option_64` is the no-fee full option.
- **Output given:** Safe-now amount ZAR 9,152; `affordable_later`; wait; full payment on 2025-07-15; no changes.
- **Rule implied:** Uncredited prize proceeds are not confirmed income. Wait for a supported future date rather than using speculative windfall money.

### request_24 / user_24
- **Inputs seen:** INR 85,045 available and INR 51,000 minimum. Rent `event_2083`, transport, dining, and scheduled insurance `event_2166` are visible. `message_17` says prior prize proceeds have already arrived and the claim is closed, with no future payments promised. Only partial payment is accepted.
- **Output given:** Safe-now amount INR 13,420; `not_affordable`; `not_recommended`; no plan.
- **Rule implied:** A past confirmed credit may be used, but no new income may be invented from a closed prize claim. The accepted payment method and recurring protected obligations still control feasibility.

### request_25 / user_25
- **Inputs seen:** IDR 32,063,050 available and IDR 23,379,100 minimum. Rent `event_2207`, transport, and a failed subscription debit `event_2287` are near the request. Scheduled salary `event_2288` is USD 1,800 against an IDR home currency and requires the dated USD→IDR rate. The user accepts full payment and installments, but the request is far above safe capacity.
- **Output given:** Safe-now amount IDR 1,425,000; `not_affordable`; `not_recommended`; no plan.
- **Rule implied:** Foreign-currency confirmed income must use the exact dated exchange-rate direction; failed events are excluded; neither conversion nor future income can overcome an unsafe 90-day plan.

## Status coverage gate

All four statuses present in the samples have concrete examples:

- `affordable_now`: request_01 and request_09, where full payment is accepted and safe on the request date.
- `affordable_with_plan`: request_02 (installments), request_06 (permitted stop), request_11 (permitted reduction), and request_19 (partial payment).
- `affordable_later`: request_03, request_04, request_08, request_13, request_18, and request_23, where waiting for a safe future date is possible.
- `not_affordable`: request_05, request_10, request_14, request_15, request_20, request_24, and request_25, where no accepted complete plan is safe in the forecast.

## Unresolved or not hand-reproducible from Stage 0 alone

These are recorded rather than guessed:

1. `event_1442` / `image_02` has multiple plausible amount fields (INR 200,000 total, INR 100,000 received, INR 100,000 balance due). The likely payable amount is the balance due, but the field-selection rule belongs in the later extraction stage.
2. `event_1700` / `image_04` shows an INR 2,854 item bill but is cropped before the final order total, so the final payable amount cannot be confirmed from the supplied view.
3. The exact forecast arithmetic behind the safe-now decimal values and dates cannot be reproduced reliably by hand without implementing the 90-day curve. In particular, request_13, request_14, request_15, request_18, request_23, and request_25 need the later deterministic forecast to validate their exact first-safe dates.
4. Requests with blank image-backed events (`request_03`, `request_16`, `request_17`, `request_19`, and `request_20`) are directionally explainable from the visible documents, but their extraction and integration must be tested separately before being used in a final pipeline.

No unresolved item is being converted into a rule or fallback in Stage 0/1.
