# HTTP API

Use `https://snaptask.dtcdev.click` and send an API token in the `Authorization: Bearer <token>` header. Browser sessions use a secure HTTP-only cookie and require the matching Origin header for writes. Every task and attachment belongs to the authenticated user.

## Tasks and attachments

Call these endpoints with JSON request bodies:

| Method | Path | Request or response |
| --- | --- | --- |
| GET | `/api/me` | User ID and display name |
| GET | `/api/tasks` | `{tasks: [...]}` |
| POST | `/api/tasks` | `{title, notes, status?}` → task |
| POST | `/api/ingest` | Same as task creation; incoming webhook endpoint |
| GET | `/api/tasks/{id}` | Task and file metadata |
| PATCH | `/api/tasks/{id}` | Update title, notes, result, or status |
| DELETE | `/api/tasks/{id}` | Delete task and stored attachments |
| POST | `/api/tasks/claim` | `{agent}` → `{task: ...}` or `{task: null}` |
| POST | `/api/tasks/{id}/heartbeat` | `{agent, claim_token}` → renewed task |
| POST | `/api/tasks/{id}/uploads` | `{name, content_type, size}` → `{file_id, upload_url}` |
| POST | `/api/tasks/{id}/uploads/{file_id}/complete` | Verify uploaded file and attach it |
| GET | `/api/tasks/{id}/files/{file_id}` | `{download_url}` valid for five minutes |

Create photo batches with `status: uploading`; text tasks default to `todo`. Reserve each file, PUT its bytes to the signed upload URL using the declared content type and exact byte size, then confirm each upload. Finally PATCH the task with `{status: "todo", publish: true}`. Agents cannot claim a staged batch, and publishing fails while a reserved upload is unfinished.

Send an `Idempotency-Key` header when creating a batch or reserving each file so retries reuse the same task or attachment. Upload URLs expire after 15 minutes; repeat the reservation with the same key to get a fresh URL. Reservations expire after one day. Attachments must be between one byte and 25 MB.

Claims last 15 minutes. Save the returned `claim_token`, then renew before `lease_until` with the same agent name. API clients changing a claimed task's status must include its current claim token. Complete work with `{status: "done", claim_token: "...", result: "..."}`. An expired claim can be taken by another agent.

## API tokens and event receivers

Manage tokens and webhooks through these endpoints:

| Method | Path | Request or response |
| --- | --- | --- |
| GET | `/api/tokens` | `{tokens: [...]}` with token metadata |
| POST | `/api/tokens` | `{name}` → metadata plus one-time `token` |
| DELETE | `/api/tokens/{id}` | Revoke a token |
| GET | `/api/webhooks` | `{webhooks: [...]}` |
| POST | `/api/webhooks` | `{url}` → metadata plus one-time signing `secret` |
| DELETE | `/api/webhooks/{id}` | Remove a receiver |

API tokens grant access to the user's tasks and integration settings. Save tokens and webhook secrets privately when created. Webhook receivers must use HTTPS on port 443 and resolve to public IP addresses; redirects are rejected.

The outgoing JSON body contains `{id, type, task}`. Events include `task.created`, `task.ready`, and `task.updated`. Staged batch changes are held until the task is ready. Incoming webhook callers can use `/api/ingest` with bearer authentication; attachments follow the same upload protocol.

Verify these outgoing headers against the raw request body:

- `X-SnapTask-Event-ID`: stable event identifier for deduplication.
- `X-SnapTask-Timestamp`: Unix seconds when this delivery was signed.
- `X-SnapTask-Signature`: `sha256=` followed by hex HMAC-SHA256.

Compute HMAC-SHA256 with the receiver's secret over the timestamp, a literal period, and the raw body bytes. Compare signatures in constant time and reject timestamps outside your chosen replay window, such as five minutes. A receiver should return a 2xx response only after durably accepting the event. Duplicate event IDs can be acknowledged without processing again.

DynamoDB Streams drives delivery with at least once semantics. Failed deliveries retry up to five times and are retained in the deployment's `FailedWebhooksQueue` after retries are exhausted. Successful receiver deliveries are recorded for seven days to reduce duplicate sends. An event delivery does not claim a task; use the claim API before starting work.

## Errors

Use the HTTP status and `{error: "..."}` body to handle failures. The API returns 400 for invalid input, 401 for missing or invalid authentication and claim credentials, 404 for unavailable resources, 409 for concurrent changes, and 500 for an internal storage failure. Retry temporary errors with backoff; reuse idempotency keys for upload operations.
