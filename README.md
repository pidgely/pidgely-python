<p align="center">
  <a href="https://pidgely.com"><img src="https://raw.githubusercontent.com/pidgely/.github/main/assets/banner.png" alt="Pidgely — Email API for developers" width="100%"></a>
</p>

<p align="center">
  <a href="https://github.com/pidgely/pidgely-python/actions/workflows/ci.yml"><img src="https://github.com/pidgely/pidgely-python/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/pidgely/"><img src="https://img.shields.io/pypi/v/pidgely?color=E2793F" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-%E2%89%A53.9-3776AB?logo=python&logoColor=white" alt="Python ≥ 3.9">
  <img src="https://img.shields.io/badge/typed-mypy%20strict-success" alt="Typed">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT"></a>
</p>

# pidgely

The official Python SDK for [Pidgely](https://pidgely.com), the Resend-compatible email API.

- **Drop-in for Resend.** The same module API as the `resend` package (`pidgely.Emails.send({...})`), plus a client object. Migrating means changing an import and a key.
- **Sync and async.** `pidgely.Pidgely` and `pidgely.AsyncPidgely`, built on `httpx` (the only dependency).
- **Typed.** `TypedDict` parameters and responses, `py.typed`, checked with mypy strict. Python 3.9+.
- **Built for production.** Idempotency keys, automatic retries with backoff that honour `Retry-After`, per-attempt timeouts.
- **Webhook verification.** Standard Webhooks (Svix) signatures, checked in constant time with timestamp tolerance.

Full documentation lives at **[docs.pidgely.com](https://docs.pidgely.com)**.

## Install

```sh
pip install pidgely
# uv add pidgely · poetry add pidgely
```

## Quickstart

Create an API key in the [dashboard](https://app.pidgely.com), verify a sending domain, then:

```python
import os
import pidgely

pidgely.api_key = os.environ["PIDGELY_API_KEY"]

email = pidgely.Emails.send(
    {
        "from": "Acme <hello@acme.com>",
        "to": "ana@example.org",
        "subject": "Welcome to Acme",
        "html": "<p>Your account is ready.</p>",
    }
)
print(email["id"])
```

Prefer an explicit client (several keys, dependency injection, async)? Every resource is also available on a client, with snake_case attribute names:

```python
from pidgely import Pidgely

client = Pidgely(api_key=os.environ["PIDGELY_API_KEY"])  # or Pidgely() to read PIDGELY_API_KEY
client.emails.send({...})
```

```python
from pidgely import AsyncPidgely

async with AsyncPidgely() as client:
    await client.emails.send({...})
```

### Configuration

```python
client = Pidgely(
    api_key="pdg_...",  # default: PIDGELY_API_KEY
    base_url="https://api.pidgely.com",  # default: PIDGELY_BASE_URL
    timeout=30,  # seconds per attempt (0 disables)
    max_retries=2,  # automatic retries, see below
    user_agent="my-app/1.2.3",  # appended to pidgely-python/<version>
    default_headers={"X-Team": "growth"},
    http_client=httpx.Client(proxy="http://proxy:3128"),  # optional, bring your own
)
```

The module API reads `pidgely.api_key`, `pidgely.base_url`, `pidgely.timeout` and `pidgely.max_retries` (falling back to the environment variables) and rebuilds its client when they change.

| Environment variable | Used for |
|---|---|
| `PIDGELY_API_KEY` | API key when none is given |
| `PIDGELY_BASE_URL` | Base URL when none is given (default `https://api.pidgely.com`) |

The API key never appears in the client's `repr`, in log output or in raised errors.

### Errors

Methods return the API's JSON as plain `dict`s (typed with `TypedDict`) and raise on failure:

```python
try:
    pidgely.Emails.send({...})
except pidgely.ValidationError as e:  # 400 / 422
    print(e.status_code, e.name, e.message)
except pidgely.RateLimitError as e:  # 429
    print(e.headers.get("retry-after"))
except pidgely.PidgelyError as e:  # everything else
    ...
```

| Exception | When |
|---|---|
| `ValidationError` | 400, 422 |
| `AuthenticationError` | 401 |
| `PermissionDeniedError` | 403 |
| `NotFoundError` | 404 |
| `ConflictError` | 409 (e.g. idempotency key reused with another body) |
| `RateLimitError` | 429 |
| `InternalServerError` | 5xx |
| `APIConnectionError` / `APITimeoutError` | no response (`status_code` is `None`) |
| `MissingApiKeyError` | no API key configured |

All of them extend `PidgelyError`, which has `status_code`, `name` (machine-readable: `validation_error`, `not_found`, `invalid_api_key`, `rate_limit_exceeded`, `daily_quota_exceeded`, ...), `message` and `headers`.

Every method takes an optional last argument with request options: `idempotency_key`, `headers`, `timeout` and `max_retries`.

### Idempotency

```python
pidgely.Emails.send(
    {"from": "Acme <billing@acme.com>", "to": "ana@example.com", "subject": "Receipt #1042", "html": html},
    {"idempotency_key": "receipt-1042"},
)
```

The key is sent as `Idempotency-Key`. For 24 hours the API replays the stored response for the same key (the reply carries the header `idempotent-replayed: true`) and answers `409` when the body differs.

### Retries

Failed requests are retried up to `max_retries` times (default 2) with exponential backoff and jitter (0.5 s, 1 s, 2 s and so on, capped at 8 s), or after the delay given in `Retry-After`:

| Failure | Retried when |
|---|---|
| `408`, `429`, `500`, `502`, `503`, `504`, network error, timeout | `GET`, `PATCH`, `DELETE`, or a `POST` that has an `idempotency_key` |

**A `POST` without an idempotency key is never retried**, whatever the failure, because the email might already have been accepted. Pass an `idempotency_key` to make sends safe to retry. Quota errors (`daily_quota_exceeded`, `monthly_quota_exceeded`) are never retried, and a `Retry-After` longer than 60 seconds raises instead of waiting.

## Resources

Parameters use the API's snake_case keys. Examples use the module API; with a client, replace `pidgely.Emails` by `client.emails`, `pidgely.ApiKeys` by `client.api_keys` and so on (`client.audiences` is the alias of `client.segments`). List methods take `{"limit", "after", "before"}` (cursor pagination) and return `{"object": "list", "has_more", "data"}`.

### Emails

```python
email = pidgely.Emails.send(
    {
        "from": "Acme <hello@acme.com>",
        "to": ["ana@example.com"],
        "cc": "team@acme.com",
        "reply_to": "support@acme.com",
        "subject": "Your invoice",
        "html": "<p>Invoice attached.</p>",  # `text` is generated when omitted
        "attachments": [
            {"filename": "invoice.pdf", "content": pdf_bytes},  # bytes or base64 string
            {"filename": "logo.png", "path": "https://acme.com/logo.png", "content_id": "logo"},  # <img src="cid:logo">
        ],
        "tags": [{"name": "category", "value": "billing"}],
        "headers": {"X-Entity-Ref-ID": "inv_1042"},
        "scheduled_at": "tomorrow at 9am",  # ISO 8601 or natural language, up to 30 days ahead
    }
)

# Send a published template
pidgely.Emails.send(
    {
        "from": "Acme <hello@acme.com>",
        "to": "ana@example.com",
        "template": {"id": "welcome", "variables": {"NAME": "Ana", "TRIAL_DAYS": 14}},
    }
)

pidgely.Emails.get("4ef9a417-02e9-4d39-ad75-9611e0fcc33c")  # includes last_event
pidgely.Emails.list({"limit": 20})
pidgely.Emails.update({"id": email_id, "scheduled_at": "in 2 hours"})  # reschedule
pidgely.Emails.cancel(email_id)  # cancel a scheduled email
pidgely.Emails.Attachments.list({"email_id": email_id})
pidgely.Emails.Attachments.get({"email_id": email_id, "id": attachment_id})  # signed download_url, valid for 1 hour
```

### Batch

```python
result = pidgely.Batch.send(
    [
        {"from": "Acme <hello@acme.com>", "to": "ana@example.com", "subject": "Hi Ana", "html": "<p>Hi</p>"},
        {"from": "Acme <hello@acme.com>", "to": "bob@example.com", "subject": "Hi Bob", "html": "<p>Hi</p>"},
    ],
    {"idempotency_key": "digest-2026-10-12", "batch_validation": "permissive"},
)
# result["data"] → [{"id": ...}]; with "permissive", result["errors"] → [{"index", "message"}]
```

Up to 100 emails per request. `strict` (the default) sends all of them or none. `permissive` sends the valid ones and reports the invalid ones.

### Domains

```python
domain = pidgely.Domains.create({"name": "acme.com", "custom_return_path": "bounces", "tls": "opportunistic"})
for record in domain["records"]:  # DKIM TXT, return-path MX + SPF TXT, DMARC
    print(record["type"], record["name"], record["value"])

pidgely.Domains.verify(domain["id"])  # check DNS now
pidgely.Domains.get(domain["id"])  # status: not_started | pending | verified | failed
pidgely.Domains.list()
pidgely.Domains.update({"id": domain["id"], "tls": "enforced"})
pidgely.Domains.remove(domain["id"])
```

### API keys

```python
key = pidgely.ApiKeys.create({"name": "Production", "permission": "sending_access", "domain_id": domain_id})
print(key["token"])  # pdg_…, shown only once
pidgely.ApiKeys.list()
pidgely.ApiKeys.update(key["id"], {"name": "Production (web)"})
pidgely.ApiKeys.remove(key["id"])
```

### Contacts

```python
pidgely.Contacts.create(
    {
        "email": "ana@example.com",
        "first_name": "Ana",
        "last_name": "Lima",
        "properties": {"plan": "pro", "seats": 5},
        "segments": [{"id": segment_id}],
    }
)
pidgely.Contacts.list({"segment_id": segment_id, "limit": 100})
pidgely.Contacts.get({"email": "ana@example.com"})  # or get("ana@example.com") / get({"id": ...})
pidgely.Contacts.update({"email": "ana@example.com", "unsubscribed": True})  # kept in sync with the suppression list
pidgely.Contacts.remove({"email": "ana@example.com"})

pidgely.Contacts.Segments.list({"email": "ana@example.com"})
pidgely.Contacts.Segments.add({"email": "ana@example.com", "segment_id": segment_id})
pidgely.Contacts.Segments.remove({"contact_id": contact_id, "segment_id": segment_id})
```

### Segments (and legacy audiences)

```python
segment = pidgely.Segments.create({"name": "Pro customers"})
pidgely.Segments.list()
pidgely.Segments.get(segment["id"])
pidgely.Segments.update(segment["id"], {"name": "Pro & Team customers"})
pidgely.Segments.list_contacts(segment["id"], {"limit": 50})
pidgely.Segments.remove(segment["id"])
```

`pidgely.Audiences` is a deprecated alias of `pidgely.Segments`, kept for Resend compatibility. `Contacts.create/list/get/update/remove` also take a legacy `audience_id`.

### Broadcasts

```python
broadcast = pidgely.Broadcasts.create(
    {
        "segment_id": segment_id,
        "from": "Acme News <news@acme.com>",
        "subject": "What’s new in October",
        "preview_text": "Three features you asked for",
        "html": '<p>Hi {{{FIRST_NAME|there}}},</p>…<a href="{{{PIDGELY_UNSUBSCRIBE_URL}}}">Unsubscribe</a>',
        "name": "October newsletter",
    }
)

pidgely.Broadcasts.send(broadcast["id"], {"scheduled_at": "tomorrow at 10am"})  # omit to send now
pidgely.Broadcasts.cancel(broadcast["id"])
pidgely.Broadcasts.duplicate(broadcast["id"])
pidgely.Broadcasts.update(broadcast["id"], {"subject": "New subject"})  # drafts only
pidgely.Broadcasts.get(broadcast["id"])  # includes per-status stats
pidgely.Broadcasts.list()
pidgely.Broadcasts.remove(broadcast["id"])
```

Pass `"send": True` (with an optional `scheduled_at`) to `create` to send without a separate call. Every broadcast message includes RFC 8058 one-click unsubscribe. Personalisation supports `{{{FIRST_NAME|fallback}}}`, `{{{LAST_NAME}}}`, `{{{EMAIL}}}`, `{{{contact.<property>}}}` and `{{{RESEND_UNSUBSCRIBE_URL}}}` / `{{{PIDGELY_UNSUBSCRIBE_URL}}}`.

### Templates

```python
template = pidgely.Templates.create(
    {
        "name": "Welcome",
        "alias": "welcome",
        "from": "Acme <hello@acme.com>",
        "subject": "Welcome, {{{NAME}}}!",
        "html": "<p>Hi {{{NAME}}}, your trial lasts {{{TRIAL_DAYS}}} days.</p>",
        "variables": [
            {"key": "NAME", "type": "string", "fallback_value": "there"},
            {"key": "TRIAL_DAYS", "type": "number", "fallback_value": 14},
        ],
    }
)
pidgely.Templates.publish(template["id"])  # the published version is what `template` sends

pidgely.Templates.get("welcome")  # by id or alias (draft)
pidgely.Templates.update("welcome", {"subject": "Welcome aboard, {{{NAME}}}!"})
pidgely.Templates.duplicate("welcome")
pidgely.Templates.list()
pidgely.Templates.remove("welcome")
```

### Webhooks

```python
webhook = pidgely.Webhooks.create(
    {
        "endpoint": "https://acme.com/webhooks/pidgely",
        "events": ["email.delivered", "email.bounced", "email.complained"],
    }
)
print(webhook["signing_secret"])  # whsec_…, store it to verify deliveries

pidgely.Webhooks.list()
pidgely.Webhooks.get(webhook["id"])
pidgely.Webhooks.update(webhook["id"], {"status": "disabled"})
pidgely.Webhooks.rotate_signing_secret(webhook["id"])
pidgely.Webhooks.remove(webhook["id"])
```

Events: `email.sent`, `email.delivered`, `email.delivery_delayed`, `email.bounced`, `email.complained`, `email.failed`, `email.suppressed`, `domain.updated`, `contact.created`, `contact.updated`, `contact.deleted`.

### Suppressions

```python
pidgely.Suppressions.add({"email": "noreply@example.com"})
pidgely.Suppressions.list({"origin": "bounce"})  # bounce | complaint | manual | unsubscribe
pidgely.Suppressions.get("noreply@example.com")  # by id or email
pidgely.Suppressions.remove("noreply@example.com")
pidgely.Suppressions.Batch.add({"emails": ["a@example.com", "b@example.com"]})  # up to 100
pidgely.Suppressions.Batch.remove({"emails": ["a@example.com"]})
```

## Verifying webhooks

Pidgely signs every delivery with the [Standard Webhooks](https://www.standardwebhooks.com) scheme. The same values are sent under both the `webhook-*` and `svix-*` header names. `verify_webhook` checks the HMAC-SHA256 signature in constant time, rejects timestamps more than 5 minutes from now, and returns the parsed event. Pass the **raw** request body. No API key is needed.

```python
import pidgely


# Flask
@app.post("/webhooks/pidgely")
def pidgely_webhook():
    try:
        event = pidgely.verify_webhook(request.get_data(), request.headers, os.environ["PIDGELY_WEBHOOK_SECRET"])
    except pidgely.WebhookVerificationError:
        return "invalid signature", 400
    if event["type"] == "email.bounced":
        ...  # event["data"]["email_id"], event["data"]["to"], ...
    return "", 204
```

```python
# FastAPI
@app.post("/webhooks/pidgely")
async def pidgely_webhook(request: Request):
    event = pidgely.verify_webhook(await request.body(), request.headers, os.environ["PIDGELY_WEBHOOK_SECRET"])
    ...
```

`pidgely.Webhooks.verify(...)` and `client.webhooks.verify(...)` are the same function. Set a different window with `tolerance=` (seconds).

## Migrating from Resend

Pidgely serves the Resend REST API at the same paths, and this SDK mirrors the `resend` package:

```diff
- import resend
- resend.api_key = os.environ["RESEND_API_KEY"]
- resend.Emails.send({...})
+ import pidgely
+ pidgely.api_key = os.environ["PIDGELY_API_KEY"]
+ pidgely.Emails.send({...})
```

1. `pip uninstall resend && pip install pidgely`.
2. Rename the import and swap `re_…` for your `pdg_…` key.
3. Verify your domain in Pidgely and publish the DNS records it returns.
4. If you verify webhooks, use `pidgely.verify_webhook` with the `whsec_…` secret from your Pidgely webhook.

Parameter dictionaries use the same snake_case keys, and the resources keep their names (`Emails`, `Batch`, `Domains`, `ApiKeys`, `Contacts`, `Segments`/`Audiences`, `Broadcasts`, `Templates`, `Webhooks`). Errors are raised as `pidgely.PidgelyError` subclasses instead of `resend.exceptions.ResendError`. Pidgely additions include `Emails.Attachments`, `ApiKeys.update`, `Segments.update/list_contacts`, `Broadcasts.cancel/duplicate`, `Suppressions`, the `stream` field on emails, an async client and built-in retries. Some Resend features are not supported yet: open/click tracking, topics, inbound email, automations, events and logs. See the migration guide at [docs.pidgely.com](https://docs.pidgely.com) for the full list.

## Development

```sh
uv venv && uv pip install -e . --group dev   # or: pip install -e . --group dev
ruff check . && ruff format --check . && mypy
pytest --cov                                  # respx mocks, no network
python scripts/generate_async.py              # after editing resources/_sync.py
python -m build
```

`src/pidgely/resources/_async.py` is generated from `_sync.py`; CI fails when it is out of date.

### Publishing

Releases are published from GitHub Actions ([`release.yml`](.github/workflows/release.yml)) when a `v*` tag is pushed. The workflow checks that the tag matches `src/pidgely/_version.py`, runs the full checks, builds the sdist and wheel, publishes them to PyPI and creates the GitHub release.

1. One-time setup, preferred: on PyPI, add a **trusted publisher** for the project `pidgely` (owner `pidgely`, repository `pidgely-python`, workflow `release.yml`, environment `pypi`). For the very first upload use a "pending publisher". No secret is needed. Alternative: create a PyPI API token scoped to the project and save it as the repository secret `PYPI_API_TOKEN`; it is used when present.
2. Update `CHANGELOG.md` and `__version__` in `src/pidgely/_version.py`, commit, wait for CI on `main`, then `git tag v0.2.0 && git push origin v0.2.0`.

## Links

- Documentation: https://docs.pidgely.com
- API reference (OpenAPI 3.1): [`openapi/pidgely.yaml`](openapi/pidgely.yaml)
- Other SDKs: [Node.js](https://github.com/pidgely/pidgely-node) · [Go](https://github.com/pidgely/pidgely-go) · [PHP](https://github.com/pidgely/pidgely-php) · [Ruby](https://github.com/pidgely/pidgely-ruby)
- Security: see [SECURITY.md](https://github.com/pidgely/.github/blob/main/SECURITY.md)

## License

[MIT](LICENSE) © Caotec Serviços em Tecnologia Ltda
