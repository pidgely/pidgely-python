from __future__ import annotations

import base64
from typing import Any, Dict

import pytest

import pidgely
from pidgely.webhooks import sign_webhook, verify_webhook

# Official Standard Webhooks / Svix test vector.
SECRET = "whsec_MfKQ9r8GKYqrTwjUPD8ILPZIo2LaLaSw"
MSG_ID = "msg_p5jXN8AQM9LWM0D4loKWxJek"
TS = 1614265330
PAYLOAD = '{"test": 2432232314}'
SIGNATURE = "v1,g0hM9SsE+OTPJTGt/tmIKtSyZlE3uFJELVlNIOLJ1OE="
NOW = float(TS)
HEADERS = {"svix-id": MSG_ID, "svix-timestamp": str(TS), "svix-signature": SIGNATURE}


def test_sign_matches_vector() -> None:
    assert sign_webhook(SECRET, MSG_ID, TS, PAYLOAD) == SIGNATURE
    assert sign_webhook(SECRET[len("whsec_") :], MSG_ID, str(TS), PAYLOAD.encode()) == SIGNATURE


def test_verify_svix_headers() -> None:
    assert verify_webhook(PAYLOAD, HEADERS, SECRET, now=NOW) == {"test": 2432232314}


def test_verify_webhook_headers_case_insensitive_and_bytes() -> None:
    headers = {"Webhook-Id": MSG_ID, "Webhook-Timestamp": str(TS), "Webhook-Signature": SIGNATURE}
    assert verify_webhook(PAYLOAD.encode(), headers, SECRET, now=NOW) == {"test": 2432232314}
    assert verify_webhook(bytearray(PAYLOAD.encode()), headers, SECRET, now=NOW)


def test_verify_resend_style_and_list_values() -> None:
    assert verify_webhook(PAYLOAD, {"id": MSG_ID, "timestamp": str(TS), "signature": SIGNATURE}, SECRET, now=NOW)
    assert verify_webhook(PAYLOAD, {"svix-id": [MSG_ID], "svix-timestamp": str(TS), "svix-signature": [SIGNATURE]}, SECRET, now=NOW)


def test_verify_multiple_signatures() -> None:
    headers = {**HEADERS, "svix-signature": f"v1,bm90IHRoaXMgb25l {SIGNATURE} v2,other"}
    assert verify_webhook(PAYLOAD, headers, SECRET, now=NOW)


def test_verify_within_tolerance() -> None:
    assert verify_webhook(PAYLOAD, HEADERS, SECRET, now=NOW + 299)
    assert verify_webhook(PAYLOAD, HEADERS, SECRET, now=NOW - 299)


def test_client_shortcut() -> None:
    client = pidgely.Pidgely("pdg_x")
    assert client.webhooks.verify(PAYLOAD, HEADERS, SECRET, now=NOW) == {"test": 2432232314}


OTHER = "whsec_" + base64.b64encode(b"another secret value!!").decode()


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"payload": '{"test": 2432232315}'}, "No matching signature"),
        ({"secret": OTHER}, "No matching signature"),
        ({"headers": {**HEADERS, "svix-id": "msg_other"}}, "No matching signature"),
        ({"now": NOW + 301}, "too old"),
        ({"now": NOW - 301}, "too new"),
        ({"now": NOW + 11, "tolerance": 10}, "too old"),
        ({"headers": {**HEADERS, "svix-timestamp": "12abc"}}, "Invalid signature headers"),
        ({"headers": {"svix-id": MSG_ID}}, "Missing required headers"),
        ({"secret": ""}, "Missing webhook secret"),
        ({"secret": "whsec_"}, "Invalid webhook secret"),
        ({"secret": "whsec_!!!"}, "Invalid webhook secret"),
        ({"secret": "whsec_abc"}, "Invalid webhook secret"),
    ],
)
def test_verify_rejects(kwargs: Dict[str, Any], message: str) -> None:
    args: Dict[str, Any] = {"payload": PAYLOAD, "headers": HEADERS, "secret": SECRET, "now": NOW, **kwargs}
    with pytest.raises(pidgely.WebhookVerificationError, match=message):
        verify_webhook(args["payload"], args["headers"], args["secret"], now=args["now"], tolerance=args.get("tolerance", 300))


def test_rejects_non_json_payload() -> None:
    sig = sign_webhook(SECRET, MSG_ID, TS, "nope")
    with pytest.raises(pidgely.WebhookVerificationError, match="not valid JSON"):
        verify_webhook("nope", {**HEADERS, "svix-signature": sig}, SECRET, now=NOW)


def test_default_now_rejects_old_vector() -> None:
    with pytest.raises(pidgely.WebhookVerificationError, match="too old"):
        verify_webhook(PAYLOAD, HEADERS, SECRET)
