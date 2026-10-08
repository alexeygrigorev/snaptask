# Browser workflow verification

From the repository root:

```sh
uv sync --locked
uv run python -m playwright install chromium
uv run python -m pytest tests/test_web.py -q
```

The test starts a temporary static server and mocks authenticated API responses. It verifies a two-photo batch creates no task before Ready, survives reload, retries a failed upload after another reload without duplicate tasks or attachments, publishes only after all files finish, and creates a token and webhook. It also checks mobile overflow and browser errors. Desktop, mobile, completed-task, and Connections screenshots are written to the pytest temporary directory shown with `--basetemp` or a failure report.

This test checks browser behavior against the documented API contract. Backend tests separately exercise storage, auth, staging, idempotency, and claims. Browser camera hardware and live identity-provider login require a real device/session.
