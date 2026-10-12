"""Every endpoint: method, path, query and JSON body, for the sync client."""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, Optional, cast

import httpx
import pytest
import respx

import pidgely

Call = Callable[[pidgely.Pidgely], Any]

CASES = [
    # Emails
    ("emails.get", lambda c: c.emails.get("e 1"), "GET", "/emails/e%201", None, None),
    ("emails.list", lambda c: c.emails.list({"limit": 10, "after": "cur"}), "GET", "/emails", {"limit": "10", "after": "cur"}, None),
    ("emails.list empty", lambda c: c.emails.list(), "GET", "/emails", {}, None),
    ("emails.update", lambda c: c.emails.update({"id": "e1", "scheduled_at": "in 2 hours"}), "PATCH", "/emails/e1", None, {"scheduled_at": "in 2 hours"}),
    ("emails.cancel", lambda c: c.emails.cancel("e1"), "POST", "/emails/e1/cancel", None, None),
    ("emails.attachments.list", lambda c: c.emails.attachments.list({"email_id": "e1"}), "GET", "/emails/e1/attachments", {}, None),
    ("emails.Attachments.get", lambda c: c.emails.Attachments.get({"email_id": "e1", "id": "a1"}), "GET", "/emails/e1/attachments/a1", None, None),
    # Domains
    (
        "domains.create",
        lambda c: c.domains.create({"name": "acme.com", "custom_return_path": "bounces", "tls": "opportunistic"}),
        "POST",
        "/domains",
        None,
        {"name": "acme.com", "custom_return_path": "bounces", "tls": "opportunistic"},
    ),
    ("domains.get", lambda c: c.domains.get("d1"), "GET", "/domains/d1", None, None),
    ("domains.list", lambda c: c.domains.list({"before": "x"}), "GET", "/domains", {"before": "x"}, None),
    ("domains.update", lambda c: c.domains.update({"id": "d1", "tls": "enforced"}), "PATCH", "/domains/d1", None, {"tls": "enforced"}),
    ("domains.remove", lambda c: c.domains.remove("d1"), "DELETE", "/domains/d1", None, None),
    ("domains.verify", lambda c: c.domains.verify("d1"), "POST", "/domains/d1/verify", None, None),
    # API keys
    (
        "api_keys.create",
        lambda c: c.api_keys.create({"name": "Prod", "permission": "sending_access", "domain_id": "d1"}),
        "POST",
        "/api-keys",
        None,
        {"name": "Prod", "permission": "sending_access", "domain_id": "d1"},
    ),
    ("api_keys.list", lambda c: c.api_keys.list(), "GET", "/api-keys", {}, None),
    ("api_keys.update", lambda c: c.api_keys.update("k1", {"name": "New"}), "PATCH", "/api-keys/k1", None, {"name": "New"}),
    ("api_keys.remove", lambda c: c.api_keys.remove("k1"), "DELETE", "/api-keys/k1", None, None),
    # Contacts
    (
        "contacts.create",
        lambda c: c.contacts.create({"email": "ana@x.y", "first_name": "Ana", "properties": {"plan": "pro"}, "segments": [{"id": "s1"}]}),
        "POST",
        "/contacts",
        None,
        {"email": "ana@x.y", "first_name": "Ana", "properties": {"plan": "pro"}, "segments": [{"id": "s1"}]},
    ),
    (
        "contacts.create audience",
        lambda c: c.contacts.create({"email": "ana@x.y", "audience_id": "aud1"}),
        "POST",
        "/audiences/aud1/contacts",
        None,
        {"email": "ana@x.y"},
    ),
    ("contacts.list", lambda c: c.contacts.list({"segment_id": "s1", "limit": 100}), "GET", "/contacts", {"limit": "100", "segment_id": "s1"}, None),
    ("contacts.list audience", lambda c: c.contacts.list({"audience_id": "a1"}), "GET", "/contacts", {"audience_id": "a1"}, None),
    ("contacts.get str", lambda c: c.contacts.get("ana+x@x.y"), "GET", "/contacts/ana+x@x.y", None, None),
    ("contacts.get email", lambda c: c.contacts.get({"email": "ana@x.y"}), "GET", "/contacts/ana@x.y", None, None),
    ("contacts.get audience", lambda c: c.contacts.get({"email": "ana@x.y", "audience_id": "a1"}), "GET", "/audiences/a1/contacts/ana@x.y", None, None),
    (
        "contacts.update",
        lambda c: c.contacts.update({"email": "ana@x.y", "unsubscribed": True, "last_name": "Lima"}),
        "PATCH",
        "/contacts/ana@x.y",
        None,
        {"unsubscribed": True, "last_name": "Lima"},
    ),
    (
        "contacts.update audience",
        lambda c: c.contacts.update({"id": "c1", "audience_id": "a1", "first_name": None}),
        "PATCH",
        "/audiences/a1/contacts/c1",
        None,
        {"first_name": None},
    ),
    ("contacts.remove", lambda c: c.contacts.remove({"id": "c1"}), "DELETE", "/contacts/c1", None, None),
    ("contacts.segments.list", lambda c: c.contacts.segments.list({"email": "ana@x.y"}), "GET", "/contacts/ana@x.y/segments", {}, None),
    ("contacts.Segments.add", lambda c: c.contacts.Segments.add({"email": "ana@x.y", "segment_id": "s1"}), "POST", "/contacts/ana@x.y/segments/s1", None, None),
    ("contacts.segments.remove", lambda c: c.contacts.segments.remove({"contact_id": "c1", "segment_id": "s1"}), "DELETE", "/contacts/c1/segments/s1", None, None),
    # Segments / audiences
    ("segments.create", lambda c: c.segments.create({"name": "Pro"}), "POST", "/segments", None, {"name": "Pro"}),
    ("segments.list", lambda c: c.segments.list(), "GET", "/segments", {}, None),
    ("segments.get", lambda c: c.segments.get("s1"), "GET", "/segments/s1", None, None),
    ("segments.update", lambda c: c.segments.update("s1", {"name": "Team"}), "PATCH", "/segments/s1", None, {"name": "Team"}),
    ("segments.remove", lambda c: c.segments.remove("s1"), "DELETE", "/segments/s1", None, None),
    ("segments.list_contacts", lambda c: c.segments.list_contacts("s1", {"limit": 50}), "GET", "/segments/s1/contacts", {"limit": "50"}, None),
    ("audiences alias", lambda c: c.audiences.get("s1"), "GET", "/segments/s1", None, None),
    # Broadcasts
    (
        "broadcasts.create",
        lambda c: c.broadcasts.create({"segment_id": "s1", "from": "n@acme.com", "subject": "News", "html": "<p>Hi</p>", "send": True}),
        "POST",
        "/broadcasts",
        None,
        {"segment_id": "s1", "from": "n@acme.com", "subject": "News", "html": "<p>Hi</p>", "send": True},
    ),
    ("broadcasts.list", lambda c: c.broadcasts.list(), "GET", "/broadcasts", {}, None),
    ("broadcasts.get", lambda c: c.broadcasts.get("b1"), "GET", "/broadcasts/b1", None, None),
    ("broadcasts.update", lambda c: c.broadcasts.update("b1", {"subject": "New"}), "PATCH", "/broadcasts/b1", None, {"subject": "New"}),
    ("broadcasts.remove", lambda c: c.broadcasts.remove("b1"), "DELETE", "/broadcasts/b1", None, None),
    ("broadcasts.send now", lambda c: c.broadcasts.send("b1"), "POST", "/broadcasts/b1/send", None, {}),
    ("broadcasts.send later", lambda c: c.broadcasts.send("b1", {"scheduled_at": "in 1 hour"}), "POST", "/broadcasts/b1/send", None, {"scheduled_at": "in 1 hour"}),
    ("broadcasts.cancel", lambda c: c.broadcasts.cancel("b1"), "POST", "/broadcasts/b1/cancel", None, None),
    ("broadcasts.duplicate", lambda c: c.broadcasts.duplicate("b1"), "POST", "/broadcasts/b1/duplicate", None, None),
    # Templates
    (
        "templates.create",
        lambda c: c.templates.create({"name": "Welcome", "alias": "welcome", "variables": [{"key": "N", "type": "number", "fallback_value": 14}]}),
        "POST",
        "/templates",
        None,
        {"name": "Welcome", "alias": "welcome", "variables": [{"key": "N", "type": "number", "fallback_value": 14}]},
    ),
    ("templates.list", lambda c: c.templates.list(), "GET", "/templates", {}, None),
    ("templates.get", lambda c: c.templates.get("welcome"), "GET", "/templates/welcome", None, None),
    ("templates.update", lambda c: c.templates.update("welcome", {"subject": "New"}), "PATCH", "/templates/welcome", None, {"subject": "New"}),
    ("templates.remove", lambda c: c.templates.remove("welcome"), "DELETE", "/templates/welcome", None, None),
    ("templates.publish", lambda c: c.templates.publish("welcome"), "POST", "/templates/welcome/publish", None, None),
    ("templates.duplicate", lambda c: c.templates.duplicate("welcome"), "POST", "/templates/welcome/duplicate", None, None),
    # Webhooks
    (
        "webhooks.create",
        lambda c: c.webhooks.create({"endpoint": "https://acme.com/wh", "events": ["email.delivered"]}),
        "POST",
        "/webhooks",
        None,
        {"endpoint": "https://acme.com/wh", "events": ["email.delivered"]},
    ),
    ("webhooks.list", lambda c: c.webhooks.list(), "GET", "/webhooks", {}, None),
    ("webhooks.get", lambda c: c.webhooks.get("w1"), "GET", "/webhooks/w1", None, None),
    ("webhooks.update", lambda c: c.webhooks.update("w1", {"status": "disabled"}), "PATCH", "/webhooks/w1", None, {"status": "disabled"}),
    ("webhooks.remove", lambda c: c.webhooks.remove("w1"), "DELETE", "/webhooks/w1", None, None),
    ("webhooks.rotate", lambda c: c.webhooks.rotate_signing_secret("w1"), "POST", "/webhooks/w1/signing-secret/rotate", None, None),
    # Suppressions
    ("suppressions.add", lambda c: c.suppressions.add({"email": "x@y.z"}), "POST", "/suppressions", None, {"email": "x@y.z"}),
    ("suppressions.create", lambda c: c.suppressions.create({"email": "x@y.z"}), "POST", "/suppressions", None, {"email": "x@y.z"}),
    ("suppressions.list", lambda c: c.suppressions.list({"origin": "bounce"}), "GET", "/suppressions", {"origin": "bounce"}, None),
    ("suppressions.get", lambda c: c.suppressions.get("x@y.z"), "GET", "/suppressions/x@y.z", None, None),
    ("suppressions.remove", lambda c: c.suppressions.remove("x@y.z"), "DELETE", "/suppressions/x@y.z", None, None),
    ("suppressions.batch.add", lambda c: c.suppressions.batch.add({"emails": ["a@x.y"]}), "POST", "/suppressions/batch/add", None, {"emails": ["a@x.y"]}),
    ("suppressions.Batch.remove", lambda c: c.suppressions.Batch.remove({"ids": ["i1"]}), "POST", "/suppressions/batch/remove", None, {"ids": ["i1"]}),
]


@pytest.mark.parametrize(("name", "call", "method", "path", "query", "body"), CASES, ids=[c[0] for c in CASES])
def test_endpoint(
    client: pidgely.Pidgely,
    mock: respx.MockRouter,
    name: str,
    call: Call,
    method: str,
    path: str,
    query: Optional[Dict[str, str]],
    body: Optional[Any],
) -> None:
    route = mock.route().mock(return_value=httpx.Response(200, json={"object": "x", "id": "1"}))
    result = call(client)
    assert result == {"object": "x", "id": "1"}
    request = route.calls.last.request
    assert request.method == method
    assert request.url.raw_path.decode().split("?")[0] == path
    if query is not None:
        assert dict(request.url.params) == query
    if body is None:
        assert request.content == b""
        assert "content-type" not in request.headers
    else:
        assert json.loads(request.content) == body
        assert request.headers["content-type"] == "application/json"


def test_send_email(client: pidgely.Pidgely, mock: respx.MockRouter) -> None:
    route = mock.post("/emails").mock(return_value=httpx.Response(200, json={"id": "e1"}))
    result = client.emails.send(
        {
            "from": "Acme <hello@acme.com>",
            "to": ["ana@example.org"],
            "subject": "Welcome",
            "html": "<p>Hi</p>",
            "reply_to": "support@acme.com",
            "attachments": [
                {"filename": "a.txt", "content": b"hello"},
                {"filename": "b.txt", "content": [104, 105]},
                {"filename": "c.txt", "content": "aGk="},
                {"filename": "logo.png", "path": "https://acme.com/logo.png", "content_id": "logo"},
            ],
            "tags": [{"name": "category", "value": "billing"}],
            "headers": {"X-Entity-Ref-ID": "1"},
            "template": {"id": "welcome", "variables": {"N": 1}},
            "scheduled_at": "in 1 hour",
        },
        {"idempotency_key": "welcome-ana"},
    )
    assert result == {"id": "e1"}
    req = route.calls.last.request
    assert req.headers["authorization"] == "Bearer pdg_test_0123456789abcdef"
    assert req.headers["user-agent"] == f"pidgely-python/{pidgely.__version__}"
    assert req.headers["idempotency-key"] == "welcome-ana"
    assert req.headers["accept"] == "application/json"
    sent = json.loads(req.content)
    assert [a.get("content") for a in sent["attachments"]] == ["aGVsbG8=", "aGk=", "aGk=", None]
    assert sent["from"] == "Acme <hello@acme.com>"
    assert sent["template"] == {"id": "welcome", "variables": {"N": 1}}


def test_emails_create_alias(client: pidgely.Pidgely, mock: respx.MockRouter) -> None:
    mock.post("/emails").mock(return_value=httpx.Response(200, json={"id": "e2"}))
    assert client.emails.create({"to": "a@b.c"}) == {"id": "e2"}


def test_batch_send(client: pidgely.Pidgely, mock: respx.MockRouter) -> None:
    route = mock.post("/emails/batch").mock(return_value=httpx.Response(200, json={"data": [{"id": "a"}], "errors": [{"index": 1, "message": "bad"}]}))
    res = client.batch.send(
        [{"from": "a@acme.com", "to": "b@x.y", "subject": "s", "html": "h"}, {"to": "nope"}],
        {"batch_validation": "permissive", "idempotency_key": "b1"},
    )
    assert res["errors"][0]["index"] == 1
    req = route.calls.last.request
    assert req.headers["x-batch-validation"] == "permissive"
    assert req.headers["idempotency-key"] == "b1"
    assert json.loads(req.content) == [{"from": "a@acme.com", "to": "b@x.y", "subject": "s", "html": "h"}, {"to": "nope"}]
    client.batch.create([{"to": "x@y.z"}])
    assert "x-batch-validation" not in route.calls.last.request.headers


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.emails.get(""),
        lambda c: c.emails.update({"scheduled_at": "x"}),
        lambda c: c.emails.attachments.list({}),
        lambda c: c.emails.attachments.get({"email_id": "e"}),
        lambda c: c.domains.update({"tls": "enforced"}),
        lambda c: c.contacts.get({}),
        lambda c: c.contacts.get(""),
        lambda c: c.contacts.update({"first_name": "x"}),
        lambda c: c.contacts.segments.list({}),
        lambda c: c.contacts.segments.add({"email": "a@b.c"}),
        lambda c: c.templates.publish(""),
        lambda c: c.suppressions.get(""),
    ],
)
def test_missing_required(client: pidgely.Pidgely, mock: respx.MockRouter, call: Call) -> None:
    route = mock.route().mock(return_value=httpx.Response(200, json={}))
    with pytest.raises(pidgely.PidgelyError) as exc:
        call(client)
    assert exc.value.name == "missing_required_field"
    assert exc.value.status_code is None
    assert not route.called


def test_header_options(client: pidgely.Pidgely, mock: respx.MockRouter) -> None:
    route = mock.get("/domains").mock(return_value=httpx.Response(200, json={}))
    c = pidgely.Pidgely("pdg_x", base_url=pidgely_base(), user_agent="my-app/1.2", default_headers={"X-Team": "growth"})
    c.domains.list(None, {"headers": {"X-Trace": "abc"}})
    req = route.calls.last.request
    assert req.headers["user-agent"] == f"pidgely-python/{pidgely.__version__} my-app/1.2"
    assert req.headers["x-team"] == "growth"
    assert req.headers["x-trace"] == "abc"
    # The Authorization header cannot be overridden by per-request headers.
    c.domains.list(None, {"headers": {"Authorization": "Bearer other"}})
    assert route.calls.last.request.headers["authorization"] == "Bearer pdg_x"
    c.close()


def pidgely_base() -> str:
    from tests.conftest import BASE

    return BASE


def test_empty_body_returns_none(client: pidgely.Pidgely, mock: respx.MockRouter) -> None:
    mock.delete("/domains/d").mock(return_value=httpx.Response(200, content=b""))
    assert client.domains.remove("d") is None


@pytest.mark.anyio
@pytest.mark.parametrize(("name", "call", "method", "path", "query", "body"), CASES, ids=[c[0] for c in CASES])
async def test_endpoint_async(
    mock: respx.MockRouter,
    name: str,
    call: Call,
    method: str,
    path: str,
    query: Optional[Dict[str, str]],
    body: Optional[Any],
) -> None:
    from tests.conftest import API_KEY, BASE

    route = mock.route().mock(return_value=httpx.Response(200, json={"object": "x", "id": "1"}))
    async with pidgely.AsyncPidgely(API_KEY, base_url=BASE) as client:
        result = await call(cast(Any, client))
    assert result == {"object": "x", "id": "1"}
    request = route.calls.last.request
    assert request.method == method
    assert request.url.raw_path.decode().split("?")[0] == path
    if body is not None:
        assert json.loads(request.content) == body
