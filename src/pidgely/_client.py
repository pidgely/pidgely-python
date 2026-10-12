from __future__ import annotations

import asyncio
import time
from types import TracebackType
from typing import Any, Awaitable, Callable, Mapping, Optional, Type

import httpx

from ._base import _NOT_GIVEN, PreparedRequest, Settings, outcome, retry_delay
from .resources._async import (
    AsyncApiKeys,
    AsyncBatch,
    AsyncBroadcasts,
    AsyncContacts,
    AsyncDomains,
    AsyncEmails,
    AsyncSegments,
    AsyncSuppressions,
    AsyncTemplates,
    AsyncWebhooks,
)
from .resources._sync import (
    ApiKeys,
    Batch,
    Broadcasts,
    Contacts,
    Domains,
    Emails,
    Segments,
    Suppressions,
    Templates,
    Webhooks,
)
from .types import RequestOptions

__all__ = ["Pidgely", "AsyncPidgely"]


class Pidgely:
    """Synchronous Pidgely client.

    >>> client = Pidgely(api_key="pdg_...")  # or set PIDGELY_API_KEY
    >>> client.emails.send({"from": "Acme <hello@acme.com>", "to": "ana@example.org",
    ...                     "subject": "Hi", "html": "<p>Hi</p>"})

    The API key never appears in the client's ``repr`` or in raised errors.
    """

    emails: Emails
    batch: Batch
    domains: Domains
    api_keys: ApiKeys
    contacts: Contacts
    segments: Segments
    audiences: Segments
    """Deprecated alias of ``segments``, kept for Resend compatibility."""
    broadcasts: Broadcasts
    templates: Templates
    webhooks: Webhooks
    suppressions: Suppressions

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        user_agent: Optional[str] = None,
        default_headers: Optional[Mapping[str, str]] = None,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        """
        :param api_key: ``pdg_...`` key; defaults to ``PIDGELY_API_KEY``.
        :param base_url: defaults to ``PIDGELY_BASE_URL`` or ``https://api.pidgely.com``.
        :param timeout: per-attempt timeout in seconds (default 30, ``0`` disables).
        :param max_retries: automatic retries (default 2). See the README for the rules.
        :param user_agent: appended to ``pidgely-python/<version>``.
        :param default_headers: headers sent with every request.
        :param http_client: a custom ``httpx.Client`` (proxies, transports, ...).
        """
        self._settings = Settings(api_key, base_url, timeout, max_retries, user_agent, default_headers)
        self._owns_http = http_client is None
        self._http = http_client or httpx.Client()
        self._sleep: Callable[[float], None] = time.sleep
        self.emails = Emails(self)
        self.batch = Batch(self)
        self.domains = Domains(self)
        self.api_keys = ApiKeys(self)
        self.contacts = Contacts(self)
        self.segments = Segments(self)
        self.audiences = self.segments
        self.broadcasts = Broadcasts(self)
        self.templates = Templates(self)
        self.webhooks = Webhooks(self)
        self.suppressions = Suppressions(self)

    @property
    def base_url(self) -> str:
        return self._settings.base_url

    def __repr__(self) -> str:
        return f"Pidgely(base_url={self.base_url!r})"

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> Pidgely:
        return self

    def __exit__(self, exc_type: Optional[Type[BaseException]], exc: Optional[BaseException], tb: Optional[TracebackType]) -> None:
        self.close()

    def _request(
        self,
        method: str,
        path: str,
        *,
        query: Optional[Mapping[str, Any]] = None,
        body: Any = _NOT_GIVEN,
        options: Optional[RequestOptions] = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> Any:
        req = PreparedRequest(self._settings, method, path, query, body, options, headers)
        attempt = 0
        while True:
            response: Optional[httpx.Response] = None
            exc: Optional[Exception] = None
            try:
                response = self._http.request(req.method, req.url, params=req.params, headers=req.headers, content=req.content, timeout=req.httpx_timeout())
            except httpx.TransportError as e:
                exc = e
            data, error, network = outcome(self._settings, response, exc, req)
            if error is None:
                return data
            delay = retry_delay(req, error, attempt, network)
            if delay is None:
                raise error from None
            self._sleep(delay)
            attempt += 1


class AsyncPidgely:
    """Asynchronous Pidgely client, with the same resources as :class:`Pidgely`.

    >>> async with AsyncPidgely() as client:
    ...     await client.emails.send({...})
    """

    emails: AsyncEmails
    batch: AsyncBatch
    domains: AsyncDomains
    api_keys: AsyncApiKeys
    contacts: AsyncContacts
    segments: AsyncSegments
    audiences: AsyncSegments
    """Deprecated alias of ``segments``, kept for Resend compatibility."""
    broadcasts: AsyncBroadcasts
    templates: AsyncTemplates
    webhooks: AsyncWebhooks
    suppressions: AsyncSuppressions

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        user_agent: Optional[str] = None,
        default_headers: Optional[Mapping[str, str]] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self._settings = Settings(api_key, base_url, timeout, max_retries, user_agent, default_headers)
        self._owns_http = http_client is None
        self._http = http_client or httpx.AsyncClient()
        self._sleep: Callable[[float], Awaitable[None]] = asyncio.sleep
        self.emails = AsyncEmails(self)
        self.batch = AsyncBatch(self)
        self.domains = AsyncDomains(self)
        self.api_keys = AsyncApiKeys(self)
        self.contacts = AsyncContacts(self)
        self.segments = AsyncSegments(self)
        self.audiences = self.segments
        self.broadcasts = AsyncBroadcasts(self)
        self.templates = AsyncTemplates(self)
        self.webhooks = AsyncWebhooks(self)
        self.suppressions = AsyncSuppressions(self)

    @property
    def base_url(self) -> str:
        return self._settings.base_url

    def __repr__(self) -> str:
        return f"AsyncPidgely(base_url={self.base_url!r})"

    async def close(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def __aenter__(self) -> AsyncPidgely:
        return self

    async def __aexit__(self, exc_type: Optional[Type[BaseException]], exc: Optional[BaseException], tb: Optional[TracebackType]) -> None:
        await self.close()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        query: Optional[Mapping[str, Any]] = None,
        body: Any = _NOT_GIVEN,
        options: Optional[RequestOptions] = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> Any:
        req = PreparedRequest(self._settings, method, path, query, body, options, headers)
        attempt = 0
        while True:
            response: Optional[httpx.Response] = None
            exc: Optional[Exception] = None
            try:
                response = await self._http.request(req.method, req.url, params=req.params, headers=req.headers, content=req.content, timeout=req.httpx_timeout())
            except httpx.TransportError as e:
                exc = e
            data, error, network = outcome(self._settings, response, exc, req)
            if error is None:
                return data
            delay = retry_delay(req, error, attempt, network)
            if delay is None:
                raise error from None
            await self._sleep(delay)
            attempt += 1
