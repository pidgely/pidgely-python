"""Webhook signature verification (Standard Webhooks / Svix scheme).

Pidgely signs every delivery with HMAC-SHA256 and sends the values under both the
``webhook-*`` and ``svix-*`` header names.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import re
import time
from typing import Any, Mapping, Optional, Union, cast

from ._exceptions import WebhookVerificationError
from .types import WebhookEvent

__all__ = ["verify_webhook", "sign_webhook", "WebhookVerificationError", "DEFAULT_TOLERANCE"]

DEFAULT_TOLERANCE = 5 * 60
"""Maximum accepted clock difference, in seconds."""

_B64 = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")

Payload = Union[str, bytes, bytearray]


def _secret_key(secret: str) -> bytes:
    if not secret:
        raise WebhookVerificationError("Missing webhook secret")
    encoded = secret[len("whsec_") :] if secret.startswith("whsec_") else secret
    if not _B64.match(encoded):
        raise WebhookVerificationError("Invalid webhook secret")
    try:
        return base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        raise WebhookVerificationError("Invalid webhook secret") from None


def _bytes(payload: Payload) -> bytes:
    return payload.encode("utf-8") if isinstance(payload, str) else bytes(payload)


def sign_webhook(secret: str, msg_id: str, timestamp: Union[int, str], payload: Payload) -> str:
    """Computes the ``v1,<base64>`` signature of a delivery."""
    key = _secret_key(secret)
    message = f"{msg_id}.{timestamp}.".encode() + _bytes(payload)
    digest = hmac.new(key, message, hashlib.sha256).digest()
    return "v1," + base64.b64encode(digest).decode("ascii")


def _header(headers: Mapping[str, Any], name: str) -> Optional[str]:
    lower = {str(k).lower(): v for k, v in headers.items()}
    for key in (f"webhook-{name}", f"svix-{name}", name):
        value = lower.get(key)
        if value is not None:
            if isinstance(value, (list, tuple)):
                return " ".join(str(v) for v in value)
            return str(value)
    return None


def verify_webhook(
    payload: Payload,
    headers: Mapping[str, Any],
    secret: str,
    *,
    tolerance: int = DEFAULT_TOLERANCE,
    now: Optional[float] = None,
) -> WebhookEvent:
    """Verifies a webhook delivery and returns the parsed event.

    :param payload: the **raw** request body, exactly as received.
    :param headers: request headers (any mapping; ``webhook-*`` or ``svix-*`` names,
        case-insensitive), or ``{"id", "timestamp", "signature"}``.
    :param secret: the endpoint's signing secret (``whsec_…``).
    :param tolerance: maximum clock difference in seconds (default 300).
    :param now: override the current Unix time (tests).
    :raises WebhookVerificationError: when the headers are missing, the timestamp is
        outside the tolerance, or no signature matches. Signatures are compared in
        constant time.
    """
    key_check = _secret_key(secret)  # validates the secret before anything else
    del key_check
    msg_id = _header(headers, "id")
    timestamp = _header(headers, "timestamp")
    signature = _header(headers, "signature")
    if not msg_id or not timestamp or not signature:
        raise WebhookVerificationError("Missing required headers")
    if not timestamp.isdigit():
        raise WebhookVerificationError("Invalid signature headers")
    ts = int(timestamp)
    current = int(time.time() if now is None else now)
    if current - ts > tolerance:
        raise WebhookVerificationError("Message timestamp too old")
    if ts - current > tolerance:
        raise WebhookVerificationError("Message timestamp too new")

    expected = sign_webhook(secret, msg_id, timestamp, payload).encode()
    matched = False
    for candidate in signature.split():
        # Compare every candidate so timing does not reveal which one matched.
        if hmac.compare_digest(candidate.encode(), expected):
            matched = True
    if not matched:
        raise WebhookVerificationError("No matching signature found")
    try:
        return cast(WebhookEvent, json.loads(_bytes(payload)))
    except ValueError:
        raise WebhookVerificationError("Payload is not valid JSON") from None
