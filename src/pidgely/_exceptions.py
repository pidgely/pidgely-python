from __future__ import annotations

from typing import Dict, Optional

__all__ = [
    "PidgelyError",
    "APIConnectionError",
    "APITimeoutError",
    "AuthenticationError",
    "PermissionDeniedError",
    "NotFoundError",
    "ConflictError",
    "ValidationError",
    "RateLimitError",
    "InternalServerError",
    "MissingApiKeyError",
    "WebhookVerificationError",
]


class PidgelyError(Exception):
    """Base class of every error raised by the SDK.

    ``name`` is the API's machine-readable error name (``validation_error``,
    ``not_found``, ``rate_limit_exceeded``...). ``status_code`` is the HTTP status, or
    ``None`` when no response was received. The API key never appears in an error.
    """

    def __init__(
        self,
        message: str,
        *,
        name: str = "application_error",
        status_code: Optional[int] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.name = name
        self.status_code = status_code
        self.headers: Dict[str, str] = headers or {}

    def __str__(self) -> str:
        if self.status_code is None:
            return f"{self.name}: {self.message}"
        return f"{self.name} (HTTP {self.status_code}): {self.message}"

    def __repr__(self) -> str:
        return f"{type(self).__name__}(name={self.name!r}, status_code={self.status_code!r}, message={self.message!r})"


class APIConnectionError(PidgelyError):
    """The API could not be reached (DNS, connection, TLS, read errors)."""


class APITimeoutError(APIConnectionError):
    """An attempt exceeded the timeout."""


class AuthenticationError(PidgelyError):
    """401: missing or invalid API key."""


class PermissionDeniedError(PidgelyError):
    """403: restricted key, unverified domain or plan limit."""


class NotFoundError(PidgelyError):
    """404: the resource does not exist."""


class ConflictError(PidgelyError):
    """409: for example an idempotency key reused with a different body."""


class ValidationError(PidgelyError):
    """400 / 422: the request is invalid."""


class RateLimitError(PidgelyError):
    """429: rate limit or quota exceeded."""


class InternalServerError(PidgelyError):
    """5xx: the API failed."""


class MissingApiKeyError(PidgelyError):
    """No API key was given and ``PIDGELY_API_KEY`` is not set."""


class WebhookVerificationError(Exception):
    """A webhook delivery could not be verified."""


_BY_STATUS = {
    400: ValidationError,
    401: AuthenticationError,
    403: PermissionDeniedError,
    404: NotFoundError,
    409: ConflictError,
    422: ValidationError,
    429: RateLimitError,
}


def error_for_status(status: int, name: str, message: str, headers: Dict[str, str]) -> PidgelyError:
    cls = _BY_STATUS.get(status, InternalServerError if status >= 500 else PidgelyError)
    return cls(message, name=name, status_code=status, headers=headers)
