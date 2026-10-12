from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from typing import Any, Dict, List

import httpx
import pytest
import respx

import pidgely
from pidgely._base import backoff, parse_retry_after, seg
from tests.conftest import API_KEY, BASE

RATE_LIMITED = httpx.Response(429, json={"statusCode": 429, "name": "rate_limit_exceeded", "message": "slow down"})
UNAVAILABLE = httpx.Response(503, json={"statusCode": 503, "name": "internal_server_error", "message": "busy"})


def responses(*items: Any) -> List[Any]:
    return list(items)


# --------------------------------------------------------------------------- configuration


def test_env_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PIDGELY_API_KEY", "pdg_env")
    monkeypatch.setenv("PIDGELY_BASE_URL", "https://env.test/")
    c = pidgely.Pidgely()
    assert c.base_url == "https://env.test"
    assert pidgely.Pidgely("pdg_x", base_url="https://other.test/").base_url == "https://other.test"
    monkeypatch.delenv("PIDGELY_BASE_URL")
    assert pidgely.Pidgely("pdg_x").base_url == pidgely.DEFAULT_BASE_URL


def test_missing_api_key() -> None:
    with pytest.raises(pidgely.MissingApiKeyError) as exc:
        pidgely.Pidgely()
    assert exc.value.name == "missing_api_key"
    with pytest.raises(pidgely.MissingApiKeyError):
        pidgely.AsyncPidgely()


def test_context_manager_and_custom_http_client(mock: respx.MockRouter) -> None:
    mock.get("/domains").mock(return_value=httpx.Response(200, json={"data": []}))
    http = httpx.Client()
    with pidgely.Pidgely(API_KEY, base_url=BASE, http_client=http) as c:
        c.domains.list()
    assert not http.is_closed  # caller-owned client is not closed
    http.close()
    with pidgely.Pidgely(API_KEY, base_url=BASE) as c2:
        pass
    assert c2._http.is_closed


# --------------------------------------------------------------------------- secrets


def test_api_key_never_leaks(mock: respx.MockRouter, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    client = pidgely.Pidgely(API_KEY, base_url=BASE, max_retries=0)
    aclient = pidgely.AsyncPidgely(API_KEY, base_url=BASE)
    outputs = [repr(client), str(client), repr(aclient), repr(client._settings), repr(client.emails), repr(client.__dict__.get("_settings"))]

    mock.get("/emails/e1").mock(return_value=httpx.Response(401, json={"statusCode": 401, "name": "invalid_api_key", "message": "API key is invalid"}))
    with pytest.raises(pidgely.AuthenticationError) as auth:
        client.emails.get("e1")
    outputs += [str(auth.value), repr(auth.value), repr(auth.value.__dict__)]

    mock.get("/emails/e2").mock(side_effect=httpx.ConnectError(f"boom {API_KEY}"))
    with pytest.raises(pidgely.APIConnectionError) as conn:
        client.emails.get("e2")
    outputs += [str(conn.value), repr(conn.value), repr(conn.value.__cause__), repr(conn.value.__context__)]
    outputs.append(caplog.text)

    for out in outputs:
        assert API_KEY not in out, out
        assert "0123456789abcdef" not in out, out
    assert "[REDACTED]" in str(conn.value)
    client.close()


# --------------------------------------------------------------------------- errors


@pytest.mark.parametrize(
    ("response", "cls", "status", "name", "message"),
    [
        (httpx.Response(422, json={"statusCode": 422, "name": "validation_error", "message": "bad to"}), pidgely.ValidationError, 422, "validation_error", "bad to"),
        (httpx.Response(400, json={"name": "validation_error", "message": "bad"}), pidgely.ValidationError, 400, "validation_error", "bad"),
        (httpx.Response(404, json={"name": "not_found", "message": "nope"}), pidgely.NotFoundError, 404, "not_found", "nope"),
        (httpx.Response(403, json={"error": {"code": "forbidden", "message": "no"}}), pidgely.PermissionDeniedError, 403, "forbidden", "no"),
        (httpx.Response(403, json={"error": {"code": "forbidden"}}), pidgely.PermissionDeniedError, 403, "forbidden", "forbidden"),
        (httpx.Response(409, json={"name": "invalid_idempotent_request", "message": "x"}), pidgely.ConflictError, 409, "invalid_idempotent_request", "x"),
        (httpx.Response(429, json={"name": "daily_quota_exceeded", "message": "q"}), pidgely.RateLimitError, 429, "daily_quota_exceeded", "q"),
        (httpx.Response(501, text="<html>Bad</html>"), pidgely.InternalServerError, 501, "internal_server_error", "<html>Bad</html>"),
        (httpx.Response(418, text=""), pidgely.PidgelyError, 418, "application_error", "I'm a teapot"),
        (httpx.Response(400, json=[1]), pidgely.ValidationError, 400, "application_error", "[1]"),
    ],
)
def test_api_errors(client: pidgely.Pidgely, mock: respx.MockRouter, response: httpx.Response, cls: type, status: int, name: str, message: str) -> None:
    mock.get("/domains/d").mock(return_value=response)
    with pytest.raises(cls) as exc:
        client.domains.get("d")
    err = exc.value
    assert isinstance(err, pidgely.PidgelyError)
    assert (err.status_code, err.name, err.message) == (status, name, message)
    assert str(err) == f"{name} (HTTP {status}): {message}"
    assert isinstance(err.headers, dict)


def test_invalid_success_json(client: pidgely.Pidgely, mock: respx.MockRouter) -> None:
    mock.get("/emails/x").mock(return_value=httpx.Response(200, text="{not json"))
    with pytest.raises(pidgely.PidgelyError, match="Unable to parse the API response"):
        client.emails.get("x")


def test_timeout(client: pidgely.Pidgely, mock: respx.MockRouter) -> None:
    mock.get("/emails/x").mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(pidgely.APITimeoutError) as exc:
        client.emails.get("x", {"timeout": 1.5, "max_retries": 0})
    assert exc.value.status_code is None
    assert exc.value.name == "application_error"
    assert str(exc.value) == "application_error: Request timed out after 1.5s"


def test_timeout_is_passed_to_httpx(mock: respx.MockRouter) -> None:
    route = mock.get("/emails/x").mock(return_value=httpx.Response(200, json={}))
    c = pidgely.Pidgely(API_KEY, base_url=BASE, timeout=12)
    c.emails.get("x")
    assert route.calls.last.request.extensions["timeout"]["read"] == 12
    c.emails.get("x", {"timeout": 0})
    assert route.calls.last.request.extensions["timeout"]["read"] is None


# --------------------------------------------------------------------------- retries


def test_retries_get_on_5xx(client: pidgely.Pidgely, mock: respx.MockRouter, sleeps: List[float]) -> None:
    route = mock.get("/emails/e1").mock(side_effect=[UNAVAILABLE, UNAVAILABLE, httpx.Response(200, json={"id": "e1"})])
    assert client.emails.get("e1") == {"id": "e1"}
    assert route.call_count == 3
    assert 0.25 <= sleeps[0] <= 0.5 and 0.5 <= sleeps[1] <= 1.0


def test_stops_after_max_retries(client: pidgely.Pidgely, mock: respx.MockRouter) -> None:
    route = mock.get("/domains").mock(return_value=UNAVAILABLE)
    with pytest.raises(pidgely.InternalServerError):
        client.domains.list()
    assert route.call_count == 3


def test_max_retries_options(mock: respx.MockRouter, sleeps: List[float]) -> None:
    route = mock.get("/domains").mock(return_value=UNAVAILABLE)
    c = pidgely.Pidgely(API_KEY, base_url=BASE, max_retries=0)
    c._sleep = sleeps.append
    with pytest.raises(pidgely.InternalServerError):
        c.domains.list()
    assert route.call_count == 1
    with pytest.raises(pidgely.InternalServerError):
        c.domains.list(None, {"max_retries": 4})
    assert route.call_count == 6


@pytest.mark.parametrize("response", [UNAVAILABLE, RATE_LIMITED, httpx.Response(500, text="oops")])
def test_never_retries_post_without_idempotency_key(client: pidgely.Pidgely, mock: respx.MockRouter, response: httpx.Response) -> None:
    route = mock.post("/emails").mock(side_effect=[response, httpx.Response(200, json={"id": "dup"})])
    with pytest.raises(pidgely.PidgelyError):
        client.emails.send({"to": "a@b.c"})
    assert route.call_count == 1


def test_never_retries_post_without_key_on_network_error(client: pidgely.Pidgely, mock: respx.MockRouter, sleeps: List[float]) -> None:
    route = mock.post("/emails").mock(side_effect=httpx.ConnectError("reset"))
    with pytest.raises(pidgely.APIConnectionError):
        client.emails.send({"to": "a@b.c"})
    assert route.call_count == 1
    assert sleeps == []


def test_retries_post_with_idempotency_key(client: pidgely.Pidgely, mock: respx.MockRouter) -> None:
    route = mock.post("/emails").mock(side_effect=[UNAVAILABLE, RATE_LIMITED, httpx.ConnectError("x"), httpx.Response(200, json={"id": "e1"})])
    client._settings.max_retries = 3
    assert client.emails.send({"to": "a@b.c"}, {"idempotency_key": "k1"}) == {"id": "e1"}
    assert route.call_count == 4
    assert {c.request.headers["idempotency-key"] for c in route.calls} == {"k1"}
    assert {c.request.content for c in route.calls} == {b'{"to":"a@b.c"}'}


def test_retries_patch_and_delete(client: pidgely.Pidgely, mock: respx.MockRouter) -> None:
    patch = mock.patch("/domains/d").mock(side_effect=[UNAVAILABLE, httpx.Response(200, json={})])
    delete = mock.delete("/domains/d").mock(side_effect=[UNAVAILABLE, httpx.Response(200, json={})])
    client.domains.update({"id": "d", "tls": "enforced"})
    client.domains.remove("d")
    assert patch.call_count == 2 and delete.call_count == 2


def test_honours_retry_after(client: pidgely.Pidgely, mock: respx.MockRouter, sleeps: List[float]) -> None:
    limited = httpx.Response(429, json={"name": "rate_limit_exceeded", "message": "x"}, headers={"Retry-After": "3"})
    mock.get("/domains").mock(side_effect=[limited, httpx.Response(200, json={})])
    client.domains.list()
    assert sleeps == [3.0]


def test_retry_after_too_long(client: pidgely.Pidgely, mock: respx.MockRouter) -> None:
    limited = httpx.Response(429, json={"name": "rate_limit_exceeded", "message": "x"}, headers={"Retry-After": "120"})
    route = mock.get("/domains").mock(return_value=limited)
    with pytest.raises(pidgely.RateLimitError):
        client.domains.list()
    assert route.call_count == 1


def test_quota_errors_not_retried(client: pidgely.Pidgely, mock: respx.MockRouter) -> None:
    route = mock.get("/domains").mock(return_value=httpx.Response(429, json={"name": "monthly_quota_exceeded", "message": "q"}))
    with pytest.raises(pidgely.RateLimitError):
        client.domains.list()
    assert route.call_count == 1


def test_non_retryable_status(client: pidgely.Pidgely, mock: respx.MockRouter) -> None:
    route = mock.get("/domains").mock(return_value=httpx.Response(422, json={"name": "validation_error", "message": "x"}))
    with pytest.raises(pidgely.ValidationError):
        client.domains.list()
    assert route.call_count == 1


def test_retries_get_on_network_error(client: pidgely.Pidgely, mock: respx.MockRouter, sleeps: List[float]) -> None:
    route = mock.get("/domains").mock(side_effect=httpx.ConnectError("down"))
    with pytest.raises(pidgely.APIConnectionError, match="Unable to reach the Pidgely API: down"):
        client.domains.list()
    assert route.call_count == 3 and len(sleeps) == 2


# --------------------------------------------------------------------------- helpers


def test_parse_retry_after() -> None:
    now = datetime(2026, 10, 12, 12, 0, 0, tzinfo=timezone.utc)
    assert parse_retry_after(None) is None
    assert parse_retry_after("") is None
    assert parse_retry_after("2") == 2.0
    assert parse_retry_after("1.5") == 1.5
    assert parse_retry_after("-1") is None
    assert parse_retry_after("soon") is None
    assert parse_retry_after(format_datetime(now + timedelta(seconds=5), usegmt=True), now) == 5.0
    assert parse_retry_after(format_datetime(now - timedelta(hours=1), usegmt=True), now) == 0.0
    assert parse_retry_after("Mon, 12 Oct 2026 12:00:05", now) == 5.0  # naive date treated as UTC


def test_backoff_bounds() -> None:
    assert backoff(0, 0.0) == 0.25 and backoff(0, 1.0) == 0.5
    assert backoff(1, 1.0) == 1.0
    assert backoff(10, 1.0) == 8.0 and backoff(50, 0.0) == 4.0
    for attempt in range(8):
        value = backoff(attempt)
        cap = min(8.0, 0.5 * 2**attempt)
        assert cap / 2 <= value <= cap


def test_seg() -> None:
    assert seg("a b/c") == "a%20b%2Fc"
    assert seg("ana+x@example.com") == "ana+x@example.com"


def test_query_booleans(client: pidgely.Pidgely, mock: respx.MockRouter) -> None:
    route = mock.get("/contacts").mock(return_value=httpx.Response(200, json={}))
    params: Dict[str, Any] = {"limit": 5, "after": None}
    client.contacts.list(params)  # type: ignore[arg-type]
    assert dict(route.calls.last.request.url.params) == {"limit": "5"}
    client._request("GET", "/contacts", query={"flag": True, "off": False})
    assert dict(route.calls.last.request.url.params) == {"flag": "true", "off": "false"}
