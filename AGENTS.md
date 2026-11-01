# SnapTask

This repository owns the SnapTask photo/file queue application: backend, CLI,
web client, tests, API documentation and AWS deployment configuration.

## Agent instructions

Reusable agent instructions are maintained in the private
[bots-management repository](https://github.com/alexeygrigorev/bots-management):

- SnapTask setup, claims, downloads, lease renewal and completion:
  `.agents/skills/snaptask/SKILL.md` there.
- Google accounts, Gmail/Drive access and company source lookup:
  `.agents/skills/dapier-access/SKILL.md` there; it is the canonical procedure.
- Payment preparation: DataOps SOP
  `sop.finance.payments.prepare-payment-details-from-source`.
- N26 browser navigation and user handoff: DataOps SOP
  `sop.finance.payments.open-n26-transfer-for-user`.

Read the SOPs with `dataops kb show <id>` after activating the local CLI
environment from bots-management. Do not keep copies of these skills or
administrative procedures here. Personal context stays in bots-management's
private context area; payment records and evidence stay on their authorized task.

## Application work

- Preserve unrelated user changes. Do not deploy or rename the remote as part
  of documentation or administration work.
- Use `README.md` for development/deployment commands, `docs/api.md` for the
  API contract and `docs/clients.md` for client usage.
- Never commit tokens, credentials, private documents, screenshots or run logs.
- Use ignored `work/` only for temporary files needed by an active task; remove
  only files created by that task when they are no longer needed.
- Keep application documentation current when code changes. Outcomes and
  execution evidence belong on the relevant Hub/DataOps task.
