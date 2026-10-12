# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-10-12

### Added

- First release of the official Pidgely SDK for Python (3.9+), with `httpx` as the only dependency.
- Resend-style module API (`pidgely.api_key = ...; pidgely.Emails.send({...})`) and explicit clients: `pidgely.Pidgely` (sync) and `pidgely.AsyncPidgely` (async). Both read `PIDGELY_API_KEY` / `PIDGELY_BASE_URL`.
- Resources: `Emails` (with `Attachments`), `Batch`, `Domains`, `ApiKeys`, `Contacts` (with `Segments`), `Segments` (with the `Audiences` alias), `Broadcasts`, `Templates`, `Webhooks` and `Suppressions` (with `Batch`).
- `TypedDict` parameters and responses, `py.typed`, checked with mypy strict.
- Exceptions for every failure: `PidgelyError` and `ValidationError`, `AuthenticationError`, `PermissionDeniedError`, `NotFoundError`, `ConflictError`, `RateLimitError`, `InternalServerError`, `APIConnectionError`, `APITimeoutError`, `MissingApiKeyError`.
- `idempotency_key` request option (`Idempotency-Key` header), plus per-request `headers`, `timeout` and `max_retries`.
- Automatic retries with exponential backoff and jitter on 408/429/5xx/network errors, honouring `Retry-After`. A POST is only retried when it carries an idempotency key, so an email is never sent twice.
- Per-attempt timeouts and the `pidgely-python/<version>` user agent. The API key never appears in `repr`, logs or errors.
- `pidgely.verify_webhook` / `Webhooks.verify` for Standard Webhooks (Svix) signatures, with constant-time comparison and a 5-minute timestamp tolerance.

[Unreleased]: https://github.com/pidgely/pidgely-python/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/pidgely/pidgely-python/releases/tag/v0.1.0
