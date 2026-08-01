"""Private codec for confirm-token payloads."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any


def encode_confirm_token(family: str, version: int, payload: dict[str, Any], secret: bytes) -> str:
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")
    signature = hmac.new(secret, encoded.encode("ascii"), hashlib.sha256).hexdigest()
    return f"confirm:{family}:v{version}:{encoded}:{signature}"


def decode_confirm_token(
    token: str,
    family: str,
    version: int,
    secret: bytes,
) -> tuple[dict[str, Any] | None, str | None]:
    parts = token.split(":", 4)
    if len(parts) != 5 or parts[:3] != ["confirm", family, f"v{version}"]:
        return None, "malformed"
    encoded, signature = parts[3], parts[4]
    expected_signature = hmac.new(secret, encoded.encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        return None, "signature"
    try:
        payload = json.loads(
            base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode("utf-8")
        )
    except Exception:
        return None, "payload"
    if not isinstance(payload, dict):
        return None, "payload"
    return payload, None
