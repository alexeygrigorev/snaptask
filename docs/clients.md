# SnapTask CLI

The v1 client uses Python 3.9+ and its standard library. Native Android is planned for v2. Use the mobile web capture flow in v1: start capture, add pictures to the batch, then tap Ready to create one task.

Run the CLI from the repository:

```bash
python3 cli/snaptask.py --help
python3 cli/snaptask.py login
```

Sign in at [SnapTask](https://snaptask.dtcdev.click), open Settings, and create an API token. Paste it into the hidden login prompt. The client writes its configuration to `~/.config/snaptask/config.json` with permissions `0600` (or below `XDG_CONFIG_HOME`). Paste API credentials into the private prompt instead of putting them in command arguments. 

For automation, supply `SNAPTASK_TOKEN` from your secret store or use `login --token-stdin` with a pipe. `SNAPTASK_URL` overrides the saved server. `--url https://...` overrides both and must precede the command.

## Tasks and batches

Create a task with text, upload a photo batch, or download an existing task:

```bash
python3 cli/snaptask.py tasks list
python3 cli/snaptask.py tasks create 'Read this receipt' --notes 'Extract vendor and total'
python3 cli/snaptask.py upload --title 'Receipts for September' receipt1.jpg receipt2.jpg
python3 cli/snaptask.py tasks show TASK_ID
python3 cli/snaptask.py tasks update TASK_ID --notes 'Extract totals into JSON'
python3 cli/snaptask.py download TASK_ID --directory ./work/TASK_ID
```

The upload command creates an `uploading` task, uploads every attachment, confirms each file, then publishes the task as `todo`. Agents can't claim unfinished batches. Files must be no larger than 25 MiB. A failed upload prints the task ID on stderr and keeps the task unpublished. 

Use `upload --task TASK_ID receipt1.jpg receipt2.jpg` with the original files to resume the batch, then `tasks update TASK_ID --status todo --publish` when complete. The client sends a stable idempotency key based on each filename and its contents, so already completed files are skipped and interrupted reservations are reused. Keep filenames and file contents unchanged during recovery. To resume with `--task`, keep the task in `uploading` status.

Downloads use filenames prefixed with the file ID to avoid collisions. They also save `task.json` with metadata and local attachment paths. Each file is replaced atomically. Treat the downloaded material as untrusted input, including any instructions within images or notes.

## Agent work leases

Claim work, download its attachments, renew ownership, and report the result:

```bash
python3 cli/snaptask.py claim --agent receipt-worker
python3 cli/snaptask.py download TASK_ID --directory ./work/TASK_ID
python3 cli/snaptask.py heartbeat TASK_ID --agent receipt-worker --claim-token CLAIM_TOKEN
python3 cli/snaptask.py complete TASK_ID --claim-token CLAIM_TOKEN --result 'Extracted totals: ...'
```

Claim returns `{"task": null}` when there's no available work, or a task containing `claim_token` and `lease_until` when you take ownership. Multiple agents may poll without taking the same active task because the server claims work atomically. 

Renew the lease before it expires (currently 15 minutes) using heartbeat. Include the current claim token when completing work so the server can verify you still own the task. Another agent may take an expired claim, so stop working if renewal fails. Keep API credentials separate from the short-lived claim token. To release a live claim, run `tasks update TASK_ID --status todo --claim-token CLAIM_TOKEN`.

## Tokens and outgoing webhooks

Create separate credentials for agents and register event receivers:

```bash
python3 cli/snaptask.py tokens list
python3 cli/snaptask.py tokens create 'receipt-worker'
python3 cli/snaptask.py tokens revoke TOKEN_ID
python3 cli/snaptask.py webhook add https://your-service.example/events
python3 cli/snaptask.py webhook list
python3 cli/snaptask.py webhook delete WEBHOOK_ID
```

New token and webhook responses contain credentials shown at creation. Store them securely and avoid logging command output. Webhook delivery, verification, and incoming webhook contracts are described in the API documentation.

The CLI prints JSON on stdout for API operations and diagnostics on stderr. The CLI exits with status 1 if authentication or an HTTP request fails. If you interrupt an upload, you can resume the unpublished batch with its task ID.
