---
name: n26-transfer
description: Extract and verify payment details from invoices or SnapTask photos, sign in to N26 in Chrome using saved credentials, and open the empty transfer page for the user. Use for N26 payment preparation, navigation, and receipt interpretation.
---

# N26 transfer preparation

Prepare a concise payment sheet, sign in, and bring the user to the empty transfer entry page. The user fills the payment fields and sends the transfer. Do not create recipients, enter payment details, submit transfers, schedule payments, or authorize payments. Use existing Chrome-saved credentials through the normal login flow without exposing them. Leave PINs, confirmation codes, and mobile approval with the user.

## Chrome login and navigation

Use Chrome for N26, as requested by the user; avoid opening the in-app browser. Use the browser tools to open https://app.n26.com or reuse the existing N26 tab. The user's request to use this workflow authorizes normal login with their existing saved credentials. If Chrome autofills the login fields, submit the login form without reading or revealing the saved password. If credentials are unavailable, let the user enter them in the browser. Leave mobile login approval to the user and verify the Home page afterward.

From Home, open Send and navigate only as far as the empty bank-transfer entry form where the user can fill recipient and payment details. Follow current visible labels; do not select a saved recipient or enter any payment field. Keep the Chrome tab open for the user and provide the copyable payment sheet in chat. Login and navigation are distinct from initiating a payment.

## Source and payment details

Read the current invoice, screenshot, or task attachment directly. Extract recipient account-holder name, full IBAN, amount, currency, reference requirements, and arrival deadline. Include BIC only when supplied or required. Distinguish the beneficiary from the sender of a message and any child named in its reference. Ask about unreadable or missing required fields instead of inferring them from previous payments.

The user's son's name is Arkadij Grigorev. Use it when the current school payment requests the child's name. Derive class and purpose from the current source; do not assume a class for future payments.

Normalize IBAN whitespace and check its country length and mod-97 checksum. A valid checksum does not verify ownership. Preserve the recipient's spelling and source amount. For an arrival deadline, use the user's current date and timezone and explain any timing implications without promising settlement.

Save payment-specific details under the current task's output directory, not inside this reusable skill. Show copyable recipient, IBAN, amount, and reference in chat. Separate one-time arrears and recurring charges when the source explicitly calls for both; never infer a standing order from a one-time request.

## Guidance for the user operating N26

Check the official N26 help for current labels when needed:

- [SEPA transfer instructions](https://support.n26.com/en-eu/payments-transfers-and-withdrawals/transfers/how-to-make-a-debit-transfer)
- [Verification of Payee](https://support.n26.com/en-eu/payments-transfers-and-withdrawals/transfers/payee-verification-safe-payments)

The documented mobile flow, checked 7 October 2026, starts at Home > Send money. The user selects a recipient, or uses + > Bank Transfer to provide the account-holder name and IBAN. They enter amount and reference, select standard or instant transfer, review the details and recipient-name verification, and authorize with their own device. Adapt explanations to the actual screen the user describes. Explain any mismatch without deciding to override it on the user's behalf.

For a deadline today, explain that the user can inspect the available instant-transfer option and any displayed fee or arrival estimate. Do not guarantee delivery. Avoid suggesting duplicate submission when a transfer's status is unknown.

## Status and SnapTask handoff

If this originated in SnapTask, use the SnapTask skill for claiming, downloads, lease renewal, and release. Keep its outputs under work/<task-id>/. Release an unfinished claim when handing the payment back to the user. Do not automatically mark a transfer task complete merely because the payment sheet is ready. If the user explicitly asks to mark the task done, close it as requested and record that it was closed at the user's request, what preparation or navigation was performed, and whether payment is unverified.

After the user reports payment or provides a receipt, record exactly what is known: prepared, user-reported sent, bank-confirmed sent, or received. Do not equate a review screen, pending authorization, or scheduled order with settlement. If authorized to update SnapTask, use an accurate result and complete only the requested scope.

The earlier SnapTask payment record says N26 transfers were prepared and final authorization handed to the user; settlement was not verified. Treat that history as preparation evidence, not proof that a previous payment settled or permission to operate the bank.
