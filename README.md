# SnapTask

Turn a batch of photos into a task that an agent can claim through an API or CLI.

Open [snaptask.dtcdev.click](https://snaptask.dtcdev.click) on your phone and sign in with your approved DataTalksClub Google account. Tap Start capture, take a photo, add more photos, then tap Ready. SnapTask creates one task for the batch. Agents can claim it after every photo finishes uploading.

Your browser saves unfinished batches locally, so use the same browser and device to resume them. You can attach files up to 25 MB each.

## Connect an agent

Create an API token in the web app, then configure the CLI. Use Python 3.10 or newer to run the CLI with its standard library.

```bash
git clone https://github.com/alexeygrigorev/snaptask.git
cd snaptask
python3 cli/snaptask.py login
python3 cli/snaptask.py tasks list
python3 cli/snaptask.py claim --agent my-agent
```

The login command prompts for the token and stores it in a file readable only by your user. Automation can use `SNAPTASK_TOKEN` and optionally `SNAPTASK_URL` instead.

Open this checkout in Codex to discover the included `$snaptask` skill through `.agents/skills/snaptask`. Follow the [laptop setup guide](skills/snaptask/references/laptop.md) to authenticate and start a session, or install the skill for use in other projects.

Start by asking your agent to `Use $snaptask to check my access and list available tasks.` Read [the skill](skills/snaptask/SKILL.md) for guidance on claiming work and downloading attachments, then use it to report results from any agent.

## API and webhooks

Send `Authorization: Bearer <token>` to `/api/*` and use the [client guide](docs/clients.md) for CLI commands and request examples.

- Create tasks with `POST /api/tasks` or `POST /api/ingest`.
- Reserve an attachment with `POST /api/tasks/{id}/uploads`, PUT the file to the returned S3 URL, then confirm the upload.
- Stage photo batches with `status: uploading` and change them to `todo` after uploading every attachment.
- Claim the next available task with `POST /api/tasks/claim`.
- Register an HTTPS receiver with `POST /api/webhooks`.

Verify HMAC signatures in your webhook receiver and deduplicate events by ID. SnapTask retries failed deliveries and sends exhausted deliveries to an AWS queue for investigation.

## Develop and deploy

Install the backend dependencies and run the tests before deploying:

```bash
uv venv .venv
uv pip install --python .venv/bin/python -r backend/requirements.txt pytest 'moto[dynamodb,s3]'
.venv/bin/python -m pytest -q
./deploy/deploy.sh
```

We deploy the API to AWS Lambda and store tasks in DynamoDB with files in private S3 storage. CloudFront serves the custom domain through Route 53, with Cognito login at `auth.dtcdev.click`. The deployment script creates separate stacks for the application, OAuth client, TLS certificate, and custom domain. It requires AWS sandbox credentials and SAM CLI. It retains task and file storage if an application stack is deleted.

Use browser capture in v1 and connect agents through the API or CLI with the included skill. You can also register webhooks. A native Android capture app is planned for v2.
