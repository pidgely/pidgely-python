from __future__ import annotations

import json
from typing import Any, List

import httpx
import pytest
import respx

import pidgely
from tests.conftest import API_KEY, BASE


def test_module_api_send(mock: respx.MockRouter, monkeypatch: pytest.MonkeyPatch) -> None:
    route = mock.post("/emails").mock(return_value=httpx.Response(200, json={"id": "e1"}))
    pidgely.api_key = API_KEY
    pidgely.base_url = BASE
    result = pidgely.Emails.send({"from": "Acme <hello@acme.com>", "to": "ana@example.org", "subject": "Welcome to Acme", "html": "<p>Your account is ready.</p>"})
    assert result == {"id": "e1"}
    assert route.calls.last.request.headers["authorization"] == f"Bearer {API_KEY}"


def test_module_api_nested_and_aliases(mock: respx.MockRouter) -> None:
    pidgely.api_key = API_KEY
    pidgely.base_url = BASE
    route = mock.route().mock(return_value=httpx.Response(200, json={"ok": True}))
    pidgely.Emails.Attachments.list({"email_id": "e1"})
    assert route.calls.last.request.url.path == "/emails/e1/attachments"
    pidgely.Contacts.Segments.add({"email": "a@b.c", "segment_id": "s1"})
    assert route.calls.last.request.url.path == "/contacts/a@b.c/segments/s1"
    pidgely.Suppressions.Batch.add({"emails": ["a@b.c"]})
    assert route.calls.last.request.url.path == "/suppressions/batch/add"
    pidgely.ApiKeys.list()
    assert route.calls.last.request.url.path == "/api-keys"
    pidgely.Audiences.get("s1")
    assert route.calls.last.request.url.path == "/segments/s1"
    pidgely.Segments.list_contacts("s1", {"limit": 10})
    assert route.calls.last.request.url.path == "/segments/s1/contacts"
    pidgely.Domains.verify("d1")
    assert route.calls.last.request.url.path == "/domains/d1/verify"
    pidgely.Batch.send([{"to": "a@b.c"}])
    pidgely.Broadcasts.send("b1")
    pidgely.Templates.publish("t1")
    pidgely.Webhooks.rotate_signing_secret("w1")
    assert route.calls.last.request.url.path == "/webhooks/w1/signing-secret/rotate"
    assert "module API" in repr(pidgely.Emails)


def test_module_api_rebuilds_client_on_key_change(mock: respx.MockRouter) -> None:
    route = mock.get("/domains").mock(return_value=httpx.Response(200, json={}))
    pidgely.base_url = BASE
    pidgely.api_key = "pdg_first"
    first = pidgely.default_client()
    pidgely.Domains.list()
    assert route.calls.last.request.headers["authorization"] == "Bearer pdg_first"
    assert pidgely.default_client() is first
    pidgely.api_key = "pdg_second"
    pidgely.Domains.list()
    assert route.calls.last.request.headers["authorization"] == "Bearer pdg_second"
    assert pidgely.default_client() is not first


def test_module_api_env_key(mock: respx.MockRouter, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PIDGELY_API_KEY", "pdg_env")
    monkeypatch.setenv("PIDGELY_BASE_URL", BASE)
    route = mock.get("/domains").mock(return_value=httpx.Response(200, json={}))
    pidgely.Domains.list()
    assert route.calls.last.request.headers["authorization"] == "Bearer pdg_env"


def test_module_api_without_key() -> None:
    with pytest.raises(pidgely.MissingApiKeyError):
        pidgely.Emails.send({"to": "a@b.c"})


def test_module_webhook_verify_needs_no_key() -> None:
    from tests.test_webhooks import HEADERS, NOW, PAYLOAD, SECRET

    assert pidgely.Webhooks.verify(PAYLOAD, HEADERS, SECRET, now=NOW) == {"test": 2432232314}


# --------------------------------------------------------------------------- async


@pytest.mark.anyio
async def test_async_client(mock: respx.MockRouter) -> None:
    route = mock.post("/emails").mock(return_value=httpx.Response(200, json={"id": "e1"}))
    async with pidgely.AsyncPidgely(API_KEY, base_url=BASE) as client:
        assert repr(client) == f"AsyncPidgely(base_url={BASE!r})"
        assert API_KEY not in repr(client)
        res = await client.emails.send({"to": "a@b.c", "attachments": [{"filename": "a", "content": b"hi"}]}, {"idempotency_key": "k"})
        assert res == {"id": "e1"}
        sent = json.loads(route.calls.last.request.content)
        assert sent["attachments"][0]["content"] == "aGk="
        assert route.calls.last.request.headers["idempotency-key"] == "k"
        assert await client.emails.create({"to": "a@b.c"}) == {"id": "e1"}


@pytest.mark.anyio
async def test_async_resources(mock: respx.MockRouter) -> None:
    route = mock.route().mock(return_value=httpx.Response(200, json={"id": "x"}))
    client = pidgely.AsyncPidgely(API_KEY, base_url=BASE)
    calls: List[Any] = [
        (client.emails.attachments.get({"email_id": "e", "id": "a"}), "GET", "/emails/e/attachments/a"),
        (client.emails.Attachments.list({"email_id": "e"}), "GET", "/emails/e/attachments"),
        (client.batch.send([{"to": "a@b.c"}], {"batch_validation": "strict"}), "POST", "/emails/batch"),
        (client.domains.verify("d"), "POST", "/domains/d/verify"),
        (client.api_keys.update("k", {"name": "n"}), "PATCH", "/api-keys/k"),
        (client.contacts.Segments.remove({"email": "a@b.c", "segment_id": "s"}), "DELETE", "/contacts/a@b.c/segments/s"),
        (client.contacts.get({"email": "a@b.c"}), "GET", "/contacts/a@b.c"),
        (client.segments.list_contacts("s"), "GET", "/segments/s/contacts"),
        (client.audiences.create({"name": "n"}), "POST", "/segments"),
        (client.broadcasts.send("b", {"scheduled_at": "soon"}), "POST", "/broadcasts/b/send"),
        (client.templates.duplicate("t"), "POST", "/templates/t/duplicate"),
        (client.webhooks.rotate_signing_secret("w"), "POST", "/webhooks/w/signing-secret/rotate"),
        (client.suppressions.Batch.remove({"emails": ["a@b.c"]}), "POST", "/suppressions/batch/remove"),
        (client.suppressions.create({"email": "a@b.c"}), "POST", "/suppressions"),
        (client.batch.create([{"to": "a@b.c"}]), "POST", "/emails/batch"),
    ]
    for coro, method, path in calls:
        assert await coro == {"id": "x"}
        assert (route.calls.last.request.method, route.calls.last.request.url.path) == (method, path)
    assert client.webhooks.verify is pidgely.verify_webhook
    await client.close()


@pytest.mark.anyio
async def test_async_retries_and_errors(mock: respx.MockRouter) -> None:
    sleeps: List[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    client = pidgely.AsyncPidgely(API_KEY, base_url=BASE)
    client._sleep = fake_sleep
    unavailable = httpx.Response(503, json={"name": "internal_server_error", "message": "busy"})
    route = mock.get("/domains").mock(side_effect=[unavailable, httpx.Response(200, json={"ok": 1})])
    assert await client.domains.list() == {"ok": 1}
    assert route.call_count == 2 and len(sleeps) == 1

    post = mock.post("/emails").mock(side_effect=[unavailable, httpx.Response(200, json={"id": "dup"})])
    with pytest.raises(pidgely.InternalServerError):
        await client.emails.send({"to": "a@b.c"})
    assert post.call_count == 1

    mock.get("/emails/x").mock(side_effect=httpx.ConnectTimeout("slow"))
    with pytest.raises(pidgely.APITimeoutError):
        await client.emails.get("x", {"max_retries": 0})
    await client.close()


@pytest.mark.anyio
async def test_async_custom_http_client(mock: respx.MockRouter) -> None:
    mock.get("/domains").mock(return_value=httpx.Response(200, json={}))
    http = httpx.AsyncClient()
    client = pidgely.AsyncPidgely(API_KEY, base_url=BASE, http_client=http)
    await client.domains.list()
    await client.close()
    assert not http.is_closed
    await http.aclose()
