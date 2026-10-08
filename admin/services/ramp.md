# Ramp vendor requests

Use [Gmail through Dapier](gmail.md) to find the customer's Ramp request. Use the [Drive guide](drive.md) and [document index](../documents.md) for current company details.

## Procedure

1. Search the DataTalks.Club mailbox for Ramp messages. Verify the sender and authentication headers, customer, invoice currency, and request destination. Open the exact observed `app.ramp.com` link; do not store recipient-specific URLs or email IDs in the repository.
2. Sign in as `alexey@datatalks.club` with Google. Let Alexey complete SMS verification when prompted. Inspect current state before retrying a stalled login.
3. Reuse a saved destination whose currency matches the invoice. Revolut supports EUR, but a saved Ramp entry may have a different currency configuration. If Ramp rejects an entry, inspect its configuration; do not infer that the underlying bank cannot receive that currency.
4. If a compatible destination is missing, fetch current details from the chosen bank letterhead and add the appropriate currency destination. Avoid creating duplicate destinations. Keep each bank's IBAN/BIC together.
5. For the vendor address, use DataTalks.Club's German business address, not Revolut's Lithuanian bank address. Set Country first, then fill the address: choosing Country can reset the other fields.
6. Set the card-payment answer according to Alexey's instruction. Keep the option to make the destination the default for future requests unchecked unless explicitly requested. Ramp may recheck it after saving; verify it again.
7. Saving bank details may prompt another SMS check. Let Alexey enter the code and verify that the destination was saved.
8. Continue within the user's authorization and applicable browser rules. The Continue button can accept the [Vendor Network Agreement](https://ramp.com/legal/other-terms/other-terms/vendor-network-terms) and [Privacy Policy](https://ramp.com/legal/privacy-terms/privacy-terms/privacy-policy). Obtain any required action-time approval; report it in chat rather than maintaining an approval log.
9. Verify the completion page confirms that the customer securely received the information. Report the outcome in chat. This establishes information submission, not invoice payment.

## Source and storage rules

- Fetch current Finom and Revolut details from the document index. Finom's current bank is FINOM PAYMENTS; do not use obsolete Solaris details from cached copies.
- Fetch VAT/contact information only when the form requires it.
- Use temporary files only when needed. Keep private data outside tracked files, remove temporary task files afterward, and retain no task histories, invoice records, screenshots, or work reports in the repository.
- Keep this guide procedural. Customer details, approvals, validation incidents, and completion reports belong in chat.
