# Connections

Last checked: 2026-10-08 (Europe/Berlin).

## Dapier

- Service: https://dapier.dtcdev.click
- Local CLI source: `C:/Users/alexey/git/dapier`.
- CLI session verified as `alexey@datatalks.club`. Session storage is outside the repository at `~/.config/dapier/session.json`; never copy or print it.
- Run with `uv run --no-project python -m dapier_cli.main` from the Dapier checkout. Set `PYTHONIOENCODING=utf-8` in PowerShell for Unicode output.
- Verify access with `auth status`, `connections list --all`, and `connections show <id>`.
- Use `connections discover google-sheets files --param "query=name contains 'term'"` for Drive discovery. Query syntax is Google Drive syntax; names are case-sensitive. Discovery is bounded, so an empty broad listing does not prove a file is absent.
- `token exec <connection> --agent <existing-granted-agent> -- <command>` supplies `DAPIER_ACCESS_TOKEN` only to the child environment. Do not print it or put it in command arguments.

## Google accounts

| Connection | Verified account | Granted services / status |
|---|---|---|
| `google-sheets` | `alexey@datatalks.club` | Drive read-only, Docs, Sheets; connected. Existing `todo-cli` agent has a `use` grant. |
| `google-calendar` | `alexey.s.grigoriev@gmail.com` | Calendar, Drive, Docs, Sheets; connected. |
| `google-drive` | None | Setup incomplete; do not use as a verified account. |
| `google-gmail-datatalks` | Not yet verified | Created for Gmail lookup; consent incomplete. |

On 2026-10-08, the new Gmail connection was configured with `gmail.readonly` and `userinfo.email`. Dapier's live consent flow automatically requested **both `gmail.readonly` and `gmail.send`**. Google displayed **"Google hasn't verified this app"**. No Gmail access was granted by the agent. The user must review the warning and consent. Do not describe this connection as read-only unless readback confirms the granted scopes.

Chrome has existing Gmail sessions for the personal and DataTalks accounts. The user requested Ramp email lookup through Dapier, so finish Dapier consent before using it for that lookup.

## Slack

- DataTalks.Club member administration: https://datatalks-club.slack.com/admin.
- Chrome's existing session was verified on 2026-10-08 as administrator **Alexey Grigorev** in **DataTalks.Club**.
- Member deactivation and status readback succeeded through the browser. No Slack API/Dapier connection was established in this task.
- Follow [Slack moderation](services/slack.md) for screenshot matching, deactivation, verification, and chat reporting.
