"""Official Python SDK for the Pidgely email API (Resend-compatible).

Module API::

    import os
    import pidgely

    pidgely.api_key = os.environ["PIDGELY_API_KEY"]
    pidgely.Emails.send({"from": "Acme <hello@acme.com>", "to": "ana@example.org",
                         "subject": "Welcome to Acme", "html": "<p>Your account is ready.</p>"})

Client API::

    client = pidgely.Pidgely(api_key="pdg_...")
    client.emails.send({...})

Documentation: https://docs.pidgely.com
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, cast

from . import resources as _resources
from . import types
from ._base import DEFAULT_BASE_URL
from ._client import AsyncPidgely, Pidgely
from ._exceptions import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    ConflictError,
    InternalServerError,
    MissingApiKeyError,
    NotFoundError,
    PermissionDeniedError,
    PidgelyError,
    RateLimitError,
    ValidationError,
    WebhookVerificationError,
)
from ._module import ResourceProxy as _Proxy
from ._module import default_client
from ._version import __version__
from .webhooks import sign_webhook, verify_webhook

__all__ = [
    "__version__",
    "api_key",
    "base_url",
    "timeout",
    "max_retries",
    "Pidgely",
    "AsyncPidgely",
    "DEFAULT_BASE_URL",
    "default_client",
    "Emails",
    "Batch",
    "Domains",
    "ApiKeys",
    "Contacts",
    "Segments",
    "Audiences",
    "Broadcasts",
    "Templates",
    "Webhooks",
    "Suppressions",
    "verify_webhook",
    "sign_webhook",
    "types",
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

api_key: Optional[str] = None
"""API key for the module API. Defaults to the ``PIDGELY_API_KEY`` environment variable."""
base_url: Optional[str] = None
"""Base URL for the module API. Defaults to ``PIDGELY_BASE_URL`` or ``https://api.pidgely.com``."""
timeout: Optional[float] = None
"""Per-attempt timeout in seconds for the module API (default 30)."""
max_retries: Optional[int] = None
"""Automatic retries for the module API (default 2)."""

if TYPE_CHECKING:
    Emails: _resources.Emails
    Batch: _resources.Batch
    Domains: _resources.Domains
    ApiKeys: _resources.ApiKeys
    Contacts: _resources.Contacts
    Segments: _resources.Segments
    Audiences: _resources.Segments
    Broadcasts: _resources.Broadcasts
    Templates: _resources.Templates
    Webhooks: _resources.Webhooks
    Suppressions: _resources.Suppressions
else:
    Emails = _Proxy("emails", _resources.Emails)
    Batch = _Proxy("batch", _resources.Batch)
    Domains = _Proxy("domains", _resources.Domains)
    ApiKeys = _Proxy("api_keys", _resources.ApiKeys)
    Contacts = _Proxy("contacts", _resources.Contacts)
    Segments = _Proxy("segments", _resources.Segments)
    Audiences = _Proxy("audiences", _resources.Segments)
    Broadcasts = _Proxy("broadcasts", _resources.Broadcasts)
    Templates = _Proxy("templates", _resources.Templates)
    Webhooks = _Proxy("webhooks", _resources.Webhooks)
    Suppressions = _Proxy("suppressions", _resources.Suppressions)

del cast
