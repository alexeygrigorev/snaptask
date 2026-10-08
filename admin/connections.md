# Connections

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
| `google-gmail-datatalks` | `alexey@datatalks.club` | Gmail read and send; connected. `admin-os` agent has a `use` grant for the existing CLI subject. |

Gmail grants include both read and send access. The display name is `Gmail (DataTalks; read and send granted)`. Gmail API is enabled in Google project `dtcdev-click` (`685623962041`). Inspect actual scopes and account binding before use.

## Read helper

`admin/google_read.py` performs read-only Drive, Docs, and Gmail API calls. Invoke it through Dapier `token exec` with `uv run --no-project python <absolute-helper-path> <service> <resource> --param KEY=VALUE`. Use `google-sheets --agent todo-cli` for existing Drive access, and `google-gmail-datatalks --agent admin-os` for Gmail. Use ignored `work/` only for temporary private output and remove it after use.

## Slack

- DataTalks.Club member administration: https://datatalks-club.slack.com/admin.
- Chrome's existing session was verified on 2026-10-08 as administrator **Alexey Grigorev** in **DataTalks.Club**.
- Member deactivation and status readback succeeded through the browser. No Slack API/Dapier connection was established in this task.
- Follow [Slack moderation](services/slack.md) for screenshot matching, deactivation, verification, and chat reporting.
