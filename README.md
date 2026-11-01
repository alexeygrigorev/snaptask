# SnapTask

Photo and file tasks for agents through a web capture interface, API and CLI.

Reusable agent skills and administrative procedures are maintained in [bots-management](https://github.com/alexeygrigorev/bots-management). See [AGENTS.md](AGENTS.md) for the canonical skills and DataOps SOP identifiers.

## SnapTask image queue

Turn a batch of photos into a task that an agent can claim through an API or CLI.

Open [snaptask.dtcdev.click](https://snaptask.dtcdev.click) on your phone and sign in with your approved DataTalksClub Google account. Tap Start capture, take a photo, add more photos, then tap Ready. SnapTask creates one task for the batch. Agents can claim it after every photo finishes uploading.

Your browser saves unfinished batches locally, so use the same browser and device to resume them. You can attach files up to 25 MB each.

## Connect an agent to SnapTask

Create an API token in the web app, then configure the CLI. Use Python 3.10 or newer to run the CLI with its standard library.

```bash
git clone https://github.com/alexeygrigorev/snaptask.git
cd snaptask
python3 cli/snaptask.py login
python3 cli/snaptask.py tasks list
python3 cli/snaptask.py claim --agent my-agent
```

The login command prompts for the token and stores it in a file readable only by your user. Automation can use `SNAPTASK_TOKEN` and optionally `SNAPTASK_URL` instead.

Open the bots-management checkout in Codex to discover `$snaptask` in `.agents/skills/snaptask`. Its `references/laptop.md` covers setup; the skill uses the CLI from this application checkout. Start with `Use $snaptask to check my access and list available tasks.`

## SnapTask API and webhooks

Send `Authorization: Bearer <token>` to `/api/*` and use the [client guide](docs/clients.md) for CLI commands and request examples.

- Create tasks with `POST /api/tasks` or `POST /api/ingest`.
- Reserve an attachment with `POST /api/tasks/{id}/uploads`, PUT the file to the returned S3 URL, then confirm the upload.
- Stage photo batches with `status: uploading` and change them to `todo` after uploading every attachment.
- Claim the next available task with `POST /api/tasks/claim`.
- Register an HTTPS receiver with `POST /api/webhooks`.

Verify HMAC signatures in your webhook receiver and deduplicate events by ID. SnapTask retries failed deliveries and sends exhausted deliveries to an AWS queue for investigation.

## Develop and deploy SnapTask

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), sync the locked dependencies, and run the tests before deploying. uv manages the virtual environment and uses Python 3.13 from `.python-version`, matching the Lambda runtime:

```bash
uv sync --locked
uv run python -m playwright install chromium
uv run python -m pytest -q
uv run cfn-lint template.yaml deploy/*.yaml
./deploy/deploy.sh
```

Runtime dependencies and development tools are declared in `pyproject.toml`; `uv.lock` records their exact versions. Use `uv add PACKAGE` for runtime dependencies, `uv add --dev PACKAGE` for development tools, and `uv lock --upgrade` to update locked versions. Commit both files after changing dependencies. Deployment exports only runtime dependencies from the lockfile and installs Linux wheels for Lambda.

We deploy the API to AWS Lambda and store tasks in DynamoDB with files in private S3 storage. CloudFront serves the custom domain through Route 53, with Cognito login at `auth.dtcdev.click`. The deployment script creates separate stacks for the application, OAuth client, TLS certificate, and custom domain. It requires AWS sandbox credentials and SAM CLI. It retains task and file storage if an application stack is deleted.

Use browser capture in v1 and connect agents through the API or CLI with the skill maintained in bots-management. You can also register webhooks. A native Android capture app is planned for v2.
