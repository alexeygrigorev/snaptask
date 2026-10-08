# Company source documents

Access these records through Dapier connection `google-sheets`, verified as `alexey@datatalks.club`, using the existing `todo-cli` grant. See the [Drive guide](services/drive.md) for commands.

| Needed information | Source | Contents |
|---|---|---|
| VAT and company contact details | [DataTalks.Club letterhead - VAT Information](https://docs.google.com/document/d/1mYXdY9ubBP4lpTS-lUqqh0CA6ZnWly8IKfsNF4POxmo/edit?usp=drivesdk) | Company name, business address, VAT number, email, phone. |
| Finom payment details | [DataTalks.Club letterhead - bank information (Finom)](https://docs.google.com/document/d/1beDJyHfV5e68swhRi1OGD2f6wsw6H6K7L7p3_i5G2Lk/edit?tab=t.0) | Current FINOM PAYMENTS bank details, IBAN/BIC, recipient and business address. Ignore obsolete Solaris values in old cached copies. |
| Revolut payment details | [DataTalks.Club letterhead - bank information (Revolut)](https://docs.google.com/document/d/1LbXLTEjS_APb5X9HAyfD1a_aL3LPIVzzXpnGb9amqac/edit?usp=drivesdk) | IBAN/BIC, recipient, Revolut Bank UAB and bank address, company address. Revolut supports EUR. |

Fetch current values from the original document before filling forms. Do not mix details from different banks or substitute contractor banking/tax details for company details. Distinguish vendor address from bank address.

These records are in shared Drive content. Include `includeItemsFromAllDrives=true` and `supportsAllDrives=true` when searching through the read helper; a bounded discovery listing may omit them. Follow `nextPageToken` when needed.

Keep this index limited to reusable source titles, links/IDs, legal entities, and fields available. Store no bank numbers, tax identifiers, task outcomes, approval history, or copied private documents here.
