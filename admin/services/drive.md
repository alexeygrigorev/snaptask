# Company records through Dapier and Google Drive

Use the **DataTalks.Club account**, not the personal account, for company records. Start with the [document index](../documents.md) for known source IDs, then search Drive if the source is missing or superseded.

## Connection and setup

The verified connection is `google-sheets`, bound to `alexey@datatalks.club`. Despite its name, it grants **Drive read-only, Docs, and Sheets** access. The existing `todo-cli` agent has a `use` grant. `google-drive` is a separate, incomplete connection with no verified account; do not use it as a substitute.

```powershell
Set-Location 'C:/Users/alexey/git/dapier'
$env:PYTHONIOENCODING = 'utf-8'
$adminReadHelper = 'C:/Users/alexey/git/snaptask/admin/google_read.py'
$adminDriveWork = 'C:/Users/alexey/git/snaptask/work/drive-temp'
New-Item -ItemType Directory -Force $adminDriveWork | Out-Null

uv run --no-project python -m dapier_cli.main connections show google-sheets
uv run --no-project python -m dapier_cli.main grants list --connection google-sheets
```

Reuse this existing grant with Dapier `token exec`. It provides `DAPIER_ACCESS_TOKEN` only to the child process; never print it or copy it into a tracked file.

## Search, including shared Drives

The simple Dapier discovery command works for a bounded listing:

```powershell
uv run --no-project python -m dapier_cli.main connections discover google-sheets files --param "query=name contains 'DataTalks'"
```

Discovery can omit shared company records. Use a direct Google Drive read with the token supplied by Dapier, including shared-Drive flags:

```powershell
uv run --no-project python -m dapier_cli.main token exec google-sheets --agent todo-cli -- uv run --no-project python $adminReadHelper drive files --param "q=trashed = false and (fullText contains 'IBAN' or fullText contains 'VAT')" --param pageSize=100 --param includeItemsFromAllDrives=true --param supportsAllDrives=true --param 'fields=files(id,name,mimeType,webViewLink),nextPageToken' > "$adminDriveWork/drive-search.json"
```

Inspect returned titles, IDs, MIME types, and `webViewLink`. Follow `nextPageToken` with `--param 'pageToken=<returned-token>'` when more results are needed. Google Drive uses expressions such as `name contains 'term'`, `fullText contains 'term'`, and `'<folder-id>' in parents`; it does not use `contains(name, 'term')`.

## Read the original Google Doc

Read known documents by their exact IDs:

```powershell
# Current Finom payment source
uv run --no-project python -m dapier_cli.main token exec google-sheets --agent todo-cli -- uv run --no-project python $adminReadHelper docs documents/1beDJyHfV5e68swhRi1OGD2f6wsw6H6K7L7p3_i5G2Lk --param 'fields=title,body.content' > "$adminDriveWork/bank-updated.json"

# Revolut payment source
uv run --no-project python -m dapier_cli.main token exec google-sheets --agent todo-cli -- uv run --no-project python $adminReadHelper docs documents/1LbXLTEjS_APb5X9HAyfD1a_aL3LPIVzzXpnGb9amqac --param 'fields=title,body.content' > "$adminDriveWork/bank-revolut.json"

# Company VAT/contact source
uv run --no-project python -m dapier_cli.main token exec google-sheets --agent todo-cli -- uv run --no-project python $adminReadHelper docs documents/1mYXdY9ubBP4lpTS-lUqqh0CA6ZnWly8IKfsNF4POxmo --param 'fields=title,body.content' > "$adminDriveWork/vat.json"
```

Text is nested inside structural elements, including paragraphs and tables; extract `textRun.content` recursively. The selected `body.content` field sufficed for these letterheads. If another document's text is missing, inspect the complete Docs response and its tab structure rather than assuming it is empty.

The helper returns JSON and does not export stored PDFs, Office files, or binary attachments. Check MIME type first; use an appropriate authenticated download/export workflow or the observed Drive link in Chrome for those files. The live DataTalks Docs connection can edit documents, but these instructions only read them.

## Which source to use

| Needed information | Source | Rule |
|---|---|---|
| Current Finom bank details | [Corrected Finom letterhead](https://docs.google.com/document/d/1beDJyHfV5e68swhRi1OGD2f6wsw6H6K7L7p3_i5G2Lk/edit?tab=t.0) | FINOM PAYMENTS; fetch current IBAN/BIC. Ignore obsolete Solaris details from cached copies. |
| Revolut bank details | [Revolut letterhead](https://docs.google.com/document/d/1LbXLTEjS_APb5X9HAyfD1a_aL3LPIVzzXpnGb9amqac/edit?usp=drivesdk) | Fetch IBAN/BIC, recipient, and bank details from the source. Revolut supports EUR; also verify the destination currency in the receiving service. |
| VAT and company contact/address | [VAT letterhead](https://docs.google.com/document/d/1mYXdY9ubBP4lpTS-lUqqh0CA6ZnWly8IKfsNF4POxmo/edit?usp=drivesdk) | Read exact values before completing forms. |

Do not mix bank details from different documents. Distinguish the company's German vendor address from Revolut's Lithuanian bank address. Contractor invoices contain their recipients' IBANs/VAT numbers, not necessarily DataTalks.Club's.

Keep reusable source titles, links/IDs, legal entities, and fields in [documents.md](../documents.md). Report verification and task results in chat. Use ignored `work/` only for temporary private files, then remove them after use.
