from __future__ import annotations

import base64
import hashlib
import hmac
import json

import pytest

from qlab_mcp.write.tokens import decode_confirm_token, encode_confirm_token


SECRET = b"fixed-secret"


def _signed_token(family: str, version: int, encoded: str, secret: bytes = SECRET) -> str:
    signature = hmac.new(secret, encoded.encode("ascii"), hashlib.sha256).hexdigest()
    return f"confirm:{family}:v{version}:{encoded}:{signature}"


def test_encode_confirm_token_has_a_fixed_canonical_golden_vector() -> None:
    assert encode_confirm_token("sample", 7, {"z": "ñ", "a": 1}, SECRET) == (
        "confirm:sample:v7:eyJhIjoxLCJ6IjoiXHUwMGYxIn0:"
        "5b2224fa6cd56ccb8f17684b6d0e0f847a25ee4e79b46808b60f4072139e8182"
    )


def test_confirm_token_round_trip_returns_the_object_payload() -> None:
    payload = {"workspace_id": "ws-1", "requested": 0.8}
    token = encode_confirm_token("videoOpacity", 1, payload, SECRET)

    assert decode_confirm_token(token, "videoOpacity", 1, SECRET) == (payload, None)


def test_decode_confirm_token_rejects_malformed_family_or_version() -> None:
    token = encode_confirm_token("videoOpacity", 1, {"a": 1}, SECRET)

    assert decode_confirm_token(token, "textBasic", 1, SECRET) == (None, "malformed")
    assert decode_confirm_token(token, "videoOpacity", 2, SECRET) == (None, "malformed")


def test_decode_confirm_token_rejects_wrong_secret_or_signature() -> None:
    token = encode_confirm_token("videoOpacity", 1, {"a": 1}, SECRET)

    assert decode_confirm_token(token, "videoOpacity", 1, b"other-secret") == (None, "signature")
    assert decode_confirm_token(token[:-1] + "0", "videoOpacity", 1, SECRET) == (None, "signature")


def test_decode_confirm_token_rejects_invalid_payload_encodings() -> None:
    invalid_base64 = _signed_token("videoOpacity", 1, "%%")
    invalid_json = _signed_token(
        "videoOpacity",
        1,
        base64.urlsafe_b64encode(b"not-json").decode("ascii").rstrip("="),
    )
    non_object = _signed_token(
        "videoOpacity",
        1,
        base64.urlsafe_b64encode(json.dumps(["not", "an", "object"]).encode("utf-8"))
        .decode("ascii")
        .rstrip("="),
    )

    assert decode_confirm_token(invalid_base64, "videoOpacity", 1, SECRET) == (None, "payload")
    assert decode_confirm_token(invalid_json, "videoOpacity", 1, SECRET) == (None, "payload")
    assert decode_confirm_token(non_object, "videoOpacity", 1, SECRET) == (None, "payload")


def test_decode_confirm_token_preserves_non_ascii_segment_failure() -> None:
    with pytest.raises(UnicodeEncodeError):
        decode_confirm_token("confirm:videoOpacity:v1:é:signature", "videoOpacity", 1, SECRET)
