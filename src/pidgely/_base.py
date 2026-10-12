"""HTTP plumbing shared by the sync and async clients: auth, JSON, timeouts, retries."""

from __future__ import annotations

import base64
import json
import os
import random
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Mapping, Optional, Tuple, cast
from urllib.parse import quote

import httpx

from ._exceptions import (
    APIConnectionError,
    APITimeoutError,
    MissingApiKeyError,
    PidgelyError,
    error_for_status,
)
from ._version import __version__
from .types import RequestOptions

DEFAULT_BASE_URL = "https://api.pidgely.com"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 2

RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})
BACKOFF_BASE = 0.5
BACKOFF_CAP = 8.0
MAX_RETRY_AFTER = 60.0

_NOT_GIVEN: Any = object()


def seg(value: str) -> str:
    """Escapes a path segment (ids, emails, template aliases)."""
    return quote(str(value), safe="@+")


def backoff(attempt: int, rand: Optional[float] = None) -> float:
    """Exponential backoff with jitter: 50-100% of min(cap, base * 2**attempt)."""
    exp = min(BACKOFF_CAP, BACKOFF_BASE * (2.0 ** min(attempt, 10)))
    r = random.random() if rand is None else rand  # noqa: S311 - jitter, not cryptography
    return exp / 2 + r * exp / 2


def parse_retry_after(value: Optional[str], now: Optional[datetime] = None) -> Optional[float]:
    """``Retry-After`` in seconds or as an HTTP date, converted to seconds."""
    if not value:
        return None
    value = value.strip()
    try:
        secs = float(value)
    except ValueError:
        pass
    else:
        return secs if secs >= 0 else None
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return None
    if when is None:  # pragma: no cover - older Pythons return None instead of raising
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    return max(0.0, (when - current).total_seconds())


def page_query(params: Optional[Mapping[str, Any]], *keys: str) -> Dict[str, Any]:
    """Picks pagination (and extra) query parameters from a params dict."""
    if not params:
        return {}
    wanted = ("limit", "after", "before", *keys)
    return {k: params[k] for k in wanted if params.get(k) is not None}


def require(params: Mapping[str, Any], *keys: str) -> str:
    """Returns the first present key, or raises a ``missing_required_field`` error."""
    for key in keys:
        value = params.get(key)
        if value:
            return str(value)
    names = " or ".join(f"`{k}`" for k in keys)
    raise PidgelyError(f"Missing {names} field.", name="missing_required_field")


def require_id(value: str, name: str = "id") -> str:
    if not value:
        raise PidgelyError(f"Missing `{name}`.", name="missing_required_field")
    return value


def without(params: Mapping[str, Any], *keys: str) -> Dict[str, Any]:
    return {k: v for k, v in params.items() if k not in keys}


def email_body(params: Mapping[str, Any]) -> Dict[str, Any]:
    """Encodes ``bytes`` / byte-list attachment content as base64."""
    body = dict(params)
    attachments = body.get("attachments")
    if isinstance(attachments, list):
        out: List[Any] = []
        for att in attachments:
            if isinstance(att, Mapping):
                att = dict(att)
                content = att.get("content")
                if isinstance(content, (bytes, bytearray, list)):
                    att["content"] = base64.b64encode(bytes(content)).decode("ascii")
            out.append(att)
        body["attachments"] = out
    return body


class Settings:
    """Resolved client configuration. The API key is kept out of ``repr``."""

    __slots__ = ("_api_key", "base_url", "default_headers", "max_retries", "timeout", "user_agent")

    def __init__(
        self,
        api_key: Optional[str],
        base_url: Optional[str],
        timeout: Optional[float],
        max_retries: Optional[int],
        user_agent: Optional[str],
        default_headers: Optional[Mapping[str, str]],
    ) -> None:
        key = api_key or os.environ.get("PIDGELY_API_KEY")
        if not key:
            raise MissingApiKeyError(
                'Missing API key. Pass it as `Pidgely(api_key="pdg_...")`, set `pidgely.api_key`, or set the PIDGELY_API_KEY environment variable.',
                name="missing_api_key",
            )
        self._api_key = key
        self.base_url = (base_url or os.environ.get("PIDGELY_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = DEFAULT_TIMEOUT if timeout is None else float(timeout)
        self.max_retries = DEFAULT_MAX_RETRIES if max_retries is None else max(0, int(max_retries))
        ua = f"pidgely-python/{__version__}"
        self.user_agent = f"{ua} {user_agent}" if user_agent else ua
        self.default_headers = dict(default_headers or {})

    def __repr__(self) -> str:
        return f"Settings(base_url={self.base_url!r})"

    def redact(self, text: str) -> str:
        return text.replace(self._api_key, "[REDACTED]")


class PreparedRequest:
    __slots__ = ("can_retry", "content", "headers", "max_retries", "method", "params", "timeout", "url")

    def __init__(
        self,
        settings: Settings,
        method: str,
        path: str,
        query: Optional[Mapping[str, Any]],
        body: Any,
        options: Optional[RequestOptions],
        extra_headers: Optional[Mapping[str, str]] = None,
    ) -> None:
        opts: Mapping[str, Any] = options or {}
        self.method = method
        self.url = settings.base_url + path
        self.params = {k: _query_value(v) for k, v in (query or {}).items() if v is not None}
        headers = {
            "Accept": "application/json",
            "User-Agent": settings.user_agent,
            **settings.default_headers,
            **(extra_headers or {}),
            **dict(opts.get("headers") or {}),
            "Authorization": f"Bearer {settings._api_key}",
        }
        self.content: Optional[bytes] = None
        if body is not _NOT_GIVEN:
            headers["Content-Type"] = "application/json"
            self.content = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        idempotency_key = opts.get("idempotency_key")
        if idempotency_key:
            headers["Idempotency-Key"] = str(idempotency_key)
        self.headers = headers
        timeout = opts.get("timeout")
        self.timeout = settings.timeout if timeout is None else float(timeout)
        retries = opts.get("max_retries")
        self.max_retries = settings.max_retries if retries is None else max(0, int(retries))
        # A POST without an idempotency key is never retried: the API might already have
        # accepted it, and a retry could send the email twice.
        self.can_retry = method != "POST" or bool(idempotency_key)

    def __repr__(self) -> str:
        return f"PreparedRequest({self.method} {self.url})"

    def httpx_timeout(self) -> Optional[float]:
        return self.timeout if self.timeout > 0 else None


def _query_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def parse_error(response: httpx.Response) -> PidgelyError:
    status = response.status_code
    headers = {k.lower(): v for k, v in response.headers.items()}
    text = response.text
    try:
        body = json.loads(text)
    except ValueError:
        body = None
    if isinstance(body, dict):
        name, message = body.get("name"), body.get("message")
        if isinstance(name, str) and isinstance(message, str):
            return error_for_status(status, name, message, headers)
        native = body.get("error")
        if isinstance(native, dict) and isinstance(native.get("code"), str):
            code = native["code"]
            msg = native.get("message")
            return error_for_status(status, code, msg if isinstance(msg, str) else code, headers)
    name = "internal_server_error" if status >= 500 else "application_error"
    return error_for_status(status, name, text.strip() or response.reason_phrase or f"HTTP {status}", headers)


def parse_success(response: httpx.Response) -> Any:
    if not response.content.strip():
        return None
    try:
        return response.json()
    except ValueError:
        raise PidgelyError(
            "Unable to parse the API response",
            headers={k.lower(): v for k, v in response.headers.items()},
        ) from None


def network_error(settings: Settings, exc: Exception, timeout: float) -> PidgelyError:
    if isinstance(exc, httpx.TimeoutException):
        return APITimeoutError(f"Request timed out after {timeout:g}s")
    return APIConnectionError(f"Unable to reach the Pidgely API: {settings.redact(str(exc) or type(exc).__name__)}")


def retry_delay(req: PreparedRequest, error: PidgelyError, attempt: int, network: bool) -> Optional[float]:
    """Seconds to wait before retrying, or ``None`` to raise ``error``."""
    if attempt >= req.max_retries or not req.can_retry:
        return None
    if network:
        return backoff(attempt)
    if error.status_code not in RETRYABLE_STATUS or error.name.endswith("quota_exceeded"):
        return None
    retry_after = parse_retry_after(error.headers.get("retry-after"))
    if retry_after is None:
        return backoff(attempt)
    if retry_after > MAX_RETRY_AFTER:
        return None
    return retry_after


def outcome(settings: Settings, response: Optional[httpx.Response], exc: Optional[Exception], req: PreparedRequest) -> Tuple[Any, Optional[PidgelyError], bool]:
    """Turns an attempt into (data, error, network_failure)."""
    if exc is not None:
        return None, network_error(settings, exc, req.timeout), True
    response = cast(httpx.Response, response)
    if 200 <= response.status_code < 300:
        return parse_success(response), None, False
    return None, parse_error(response), False
