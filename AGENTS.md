# Admin OS

This repository is Alexey's workspace for ad hoc administration, with the existing SnapTask application kept alongside it.

- Read `admin/README.md` and `admin/connections.md` before administrative work. Use `admin/documents.md` to locate source documents.
- For Ramp, Gmail, company Drive, or Slack moderation work, read the matching guide in `admin/services/`. Keep these guides limited to reusable procedures.
- Prefer Dapier's CLI/API for connected services. Use Chrome for provider consent and forms when no suitable API exists.
- Verify which Google account and legal entity each source belongs to. Never substitute a contractor's bank or tax details for Alexey's.
- Reuse existing authentication and grants. Follow the browser tool's confirmation and handoff rules for new access, contracts, and financial transactions.
- Preserve existing SnapTask code, skills, and user changes unless the task requires changing them. Do not deploy, rename the remote repository, or push unrelated changes as part of administration.

## What to save

Save information that helps complete a future task:

- Reusable procedures, working commands, scripts, prerequisites, troubleshooting steps, and verification methods in `admin/services/`.
- Connection names, verified account bindings, granted agent names, actual scopes, and authentication instructions in `admin/connections.md`. Store configuration facts, not setup histories or secrets.
- Source-document titles, IDs, links, legal entities, and the fields they establish in `admin/documents.md`. Fetch current financial and tax values from the source before use; do not copy those values into the repository.
- Explicit enduring user preferences when they apply to future work. A choice or approval for one request is not automatically an enduring preference or authorization for another request.

Keep documentation procedural and current. For example, save how to find a Ramp email, choose the correct account currency, and verify submission; do not save which customer's invoice was handled or the steps taken on that occasion.

## What not to save

- Report task outcomes, approval history, errors encountered on a particular request, and outstanding steps in chat only. Do not create task logs, completion reports, audit trails, or case histories in the repository.
- Do not retain customer/invoice records, email IDs or payloads, recipient-specific form URLs, bank numbers, tax identifiers, filled forms, or private document copies in repository documentation.
- Do not retain screenshots, recordings, execution logs, or proof-of-work artifacts in the repository, including ignored folders. When a tool requires an artifact for the user-facing report, keep it outside the checkout.
- Never put passwords, bearer tokens, OAuth tokens, authentication codes, or other credentials in source files, documentation, command arguments, or logs. Reuse the existing secure authentication storage.
- Use ignored `work/` only for temporary files necessary to complete an active task. Remove files created for the task once they are no longer needed; preserve unrelated user files.

An explicit user request to save a particular report or artifact overrides the default for that item only. Do not interpret a request to document a reusable workflow as permission to retain task traces.

## Keep instructions up to date

- When instructions used for a task are outdated, incomplete, or contradicted by verified behavior or the user's correction, update them as part of completing the task. Do not leave a known stale guide for the next session.
- Correct the original guide and any affected index or cross-reference. Replace obsolete instructions rather than appending a chronological account of the fix.
- Record the reusable correction: current command, account, source, prerequisite, or behavior. Keep the incident, customer details, and approval history in chat.
- Verify updated commands or procedures when practical. If a correction cannot be verified, state the uncertainty in the guide rather than presenting a guess as fact.
- Limit changes to instructions relevant to the task; preserve unrelated documentation and user changes. Report the documentation updates briefly in chat.
