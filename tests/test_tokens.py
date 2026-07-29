from __future__ import annotations

import base64
import hashlib
import hmac
import json

import pytest

from qlab_mcp.write.tokens import decode_confirm_token, encode_confirm_token
import qlab_mcp.write.operations as write_operations
import qlab_mcp.write.text_basics as text_basics
import qlab_mcp.write.tokens as token_helpers
import qlab_mcp.write.video_appearance as video_appearance
import qlab_mcp.write.video_audio_time as video_audio_time
import qlab_mcp.write.video_opacity as video_opacity
import qlab_mcp.write.video_scalars as video_scalars
import qlab_mcp.write.video_translation as video_translation


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


def test_extracted_write_family_hook_precedence() -> None:
    assert write_operations._EXTRACTED_WRITE_FAMILIES == (
        video_opacity,
        video_translation,
        video_scalars,
        video_appearance,
        video_audio_time,
        text_basics,
    )


def test_text_basic_uses_shared_codec_with_its_existing_payload_and_secret() -> None:
    payload_args = {
        "workspace_id": "ws-1",
        "cue_ref": "cue-1",
        "cue_id": "cue-1",
        "item": {"profile": "text_basic"},
        "operation": {
            "property": "text",
            "path": "text",
            "mode": "saved",
            "risk_tier": "high",
            "capability_gate": "text_content",
        },
        "baseline": "old text",
        "requested": "new text",
    }
    payload = text_basics._phase3e_text_basic_token_payload(**payload_args)

    assert text_basics.encode_confirm_token is token_helpers.encode_confirm_token
    assert text_basics._phase3e_text_basic_confirm_token(**payload_args) == encode_confirm_token(
        "textBasic",
        text_basics.PHASE3E_TEXT_BASIC_TOKEN_VERSION,
        payload,
        text_basics._LIGHT_WRITE_TOKEN_SECRET,
    )


def test_text_basic_wrapper_matches_the_legacy_fixed_secret_token_vector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(text_basics, "_LIGHT_WRITE_TOKEN_SECRET", b"text-fixed-secret")

    assert text_basics._phase3e_text_basic_confirm_token(
        workspace_id="ws-1",
        cue_ref="cue-1",
        cue_id="cue-1",
        item={"profile": "text_basic"},
        operation={
            "property": "text",
            "path": "text",
            "mode": "saved",
            "risk_tier": "high",
            "capability_gate": "text_content",
        },
        baseline="old text",
        requested="new text",
    ) == (
        "confirm:textBasic:v1:"
        "eyJiYXNlbGluZSI6Im9sZCB0ZXh0IiwiYmFzZWxpbmVfc2hhMjU2IjoiMGE4N2VmNmU1MTUxOGY2ODU4NjY1NDZkOTcxZGQwZTkxMzUxMGEyZGQ1ZDY0OWE1ODE5YjVkMGJmOTNlZmQ5MyIsImNhcGFiaWxpdHlfZ2F0ZSI6InRleHRfY29udGVudCIsImN1ZV9pZCI6ImN1ZS0xIiwiY3VlX3JlZiI6ImN1ZS0xIiwiY3VlX3R5cGUiOiJUZXh0IiwibWNwX3NlY3JldF92ZXJzaW9uIjoxLCJtb2RlIjoic2F2ZWQiLCJvcGVyYXRpb25fa2luZCI6InZpZGVvX3BoYXNlM2VfdGV4dF9iYXNpY193cml0ZSIsInBhdGgiOiJ0ZXh0IiwicHJvZmlsZSI6InRleHRfYmFzaWMiLCJwcm9wZXJ0eSI6InRleHQiLCJyZXF1ZXN0ZWQiOiJuZXcgdGV4dCIsInJpc2tfdGllciI6ImhpZ2giLCJ2ZXJzaW9uIjoxLCJ3b3Jrc3BhY2VfaWQiOiJ3cy0xIn0:"
        "5dddab623e8f13745a73016d2d68a0572923df52fbf2966e668bf95bf0b584fd"
    )


def test_video_opacity_uses_shared_codec_with_its_existing_payload_and_secret() -> None:
    payload_args = {
        "workspace_id": "ws-1",
        "cue_ref": "cue-1",
        "cue_id": "cue-1",
        "item": {"profile": "video_basic"},
        "operation": {
            "property": "opacity",
            "path": "opacity",
            "mode": "saved",
            "risk_tier": "high",
            "capability_gate": "video_visual",
        },
        "baseline": 1.0,
        "requested": 0.8,
    }
    payload = video_opacity._token_payload(**payload_args)

    assert video_opacity.encode_confirm_token is token_helpers.encode_confirm_token
    assert video_opacity._confirm_token(**payload_args) == encode_confirm_token(
        "videoOpacity",
        video_opacity.TOKEN_VERSION,
        payload,
        video_opacity._TOKEN_SECRET,
    )
    assert not hasattr(write_operations, "_phase3_video_opacity_confirm_token")


def test_video_opacity_wrapper_matches_the_legacy_fixed_secret_token_vector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(video_opacity, "_TOKEN_SECRET", b"opacity-fixed-secret")

    assert video_opacity._confirm_token(
        workspace_id="ws-1",
        cue_ref="cue-1",
        cue_id="cue-1",
        item={"profile": "video_basic"},
        operation={
            "property": "opacity",
            "path": "opacity",
            "mode": "saved",
            "risk_tier": "high",
            "capability_gate": "video_visual",
        },
        baseline=1.0,
        requested=0.8,
    ) == (
        "confirm:videoOpacity:v1:"
        "eyJiYXNlbGluZSI6MS4wLCJiYXNlbGluZV9zaGEyNTYiOiJkMGZmNTk3NGI2YWE1MmNmNTYyYmVhNTkyMTg0MGMwMzJhODYwYTkxYTM1MTJmN2ZlOGY3NjhmNmJiZTAwNWY2IiwiY2FwYWJpbGl0eV9nYXRlIjoidmlkZW9fdmlzdWFsIiwiY3VlX2lkIjoiY3VlLTEiLCJjdWVfcmVmIjoiY3VlLTEiLCJjdWVfdHlwZSI6IlZpZGVvIiwibWNwX3NlY3JldF92ZXJzaW9uIjoxLCJtb2RlIjoic2F2ZWQiLCJvcGVyYXRpb25fa2luZCI6InZpZGVvX3BoYXNlM19vcGFjaXR5X3dyaXRlIiwicGF0aCI6Im9wYWNpdHkiLCJwcm9maWxlIjoidmlkZW9fYmFzaWMiLCJwcm9wZXJ0eSI6Im9wYWNpdHkiLCJyZXF1ZXN0ZWQiOjAuOCwicmlza190aWVyIjoiaGlnaCIsInZlcnNpb24iOjEsIndvcmtzcGFjZV9pZCI6IndzLTEifQ:"
        "379240f26ebcf72a1f652d2e020b7cb4f8cda3a4ac6314ff99638a134e5a143e"
    )


def test_video_translation_uses_shared_codec_and_leaves_no_router_codec() -> None:
    payload_args = {
        "workspace_id": "ws-1",
        "cue_ref": "cue-1",
        "cue_id": "cue-1",
        "item": {"profile": "video_basic"},
        "operation": {
            "property": "translation/x",
            "path": "translation/x",
            "mode": "saved",
            "risk_tier": "high",
            "capability_gate": "video_visual",
        },
        "baseline": 10.0,
        "requested": 20.0,
    }
    payload = video_translation._token_payload(**payload_args)

    assert video_translation.encode_confirm_token is token_helpers.encode_confirm_token
    assert video_translation._confirm_token(**payload_args) == encode_confirm_token(
        "videoTranslation",
        video_translation.TOKEN_VERSION,
        payload,
        video_translation._TOKEN_SECRET,
    )
    legacy_router_helpers = (
        "_phase3_video_translation_operation",
        "_phase3_video_translation_call_structure_error",
        "_phase3_video_translation_dry_run_errors",
        "_annotate_phase3_video_translation_operation",
        "_validate_phase3_video_translation_real_write",
        "_mark_phase3_video_translation_real_operation",
        "_refresh_phase3_video_translation_real_result",
        "_video_translation_sha256",
        "_phase3_video_translation_token_payload",
        "_phase3_video_translation_confirm_token",
        "_decode_phase3_video_translation_confirm_token",
    )
    assert not any(hasattr(write_operations, name) for name in legacy_router_helpers)


def test_video_translation_wrapper_matches_the_legacy_fixed_secret_token_vector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(video_translation, "_TOKEN_SECRET", b"translation-fixed-secret")

    assert video_translation._confirm_token(
        workspace_id="ws-1",
        cue_ref="cue-1",
        cue_id="cue-1",
        item={"profile": "video_basic"},
        operation={
            "property": "translation/x",
            "path": "translation/x",
            "mode": "saved",
            "risk_tier": "high",
            "capability_gate": "video_visual",
        },
        baseline=10.0,
        requested=20.0,
    ) == (
        "confirm:videoTranslation:v1:"
        "eyJiYXNlbGluZSI6MTAuMCwiYmFzZWxpbmVfc2hhMjU2IjoiZjFlNDIwMTlhZWNjODU4ZmZiY2NhN2ZkZGVjNTExYjc2MWI0NzQ5MTZmZGUzN2IxYTZmZjMyMWE5YjQ1OTMzMCIsImNhcGFiaWxpdHlfZ2F0ZSI6InZpZGVvX3Zpc3VhbCIsImN1ZV9pZCI6ImN1ZS0xIiwiY3VlX3JlZiI6ImN1ZS0xIiwiY3VlX3R5cGUiOiJWaWRlbyIsIm1jcF9zZWNyZXRfdmVyc2lvbiI6MSwibW9kZSI6InNhdmVkIiwib3BlcmF0aW9uX2tpbmQiOiJ2aWRlb19waGFzZTNiX3RyYW5zbGF0aW9uX3dyaXRlIiwicGF0aCI6InRyYW5zbGF0aW9uL3giLCJwcm9maWxlIjoidmlkZW9fYmFzaWMiLCJwcm9wZXJ0eSI6InRyYW5zbGF0aW9uL3giLCJyZXF1ZXN0ZWQiOjIwLjAsInJpc2tfdGllciI6ImhpZ2giLCJ2ZXJzaW9uIjoxLCJ3b3Jrc3BhY2VfaWQiOiJ3cy0xIn0:"
        "af495043d1b1ab0cd0939b73815ccbb0b834c852c7a9ad360ab7a8be2587c709"
    )


def test_video_scalars_use_shared_codec_and_leave_no_router_codec() -> None:
    payload_args = {
        "workspace_id": "ws-1",
        "cue_ref": "cue-1",
        "cue_id": "cue-1",
        "item": {"profile": "video_basic"},
        "operation": {
            "property": "scale/x",
            "path": "scale/x",
            "mode": "saved",
            "risk_tier": "high",
            "capability_gate": "video_visual",
        },
        "baseline": 1.0,
        "requested": 1.25,
    }
    payload = video_scalars._token_payload(**payload_args)

    assert video_scalars.encode_confirm_token is token_helpers.encode_confirm_token
    assert video_scalars._confirm_token(**payload_args) == encode_confirm_token(
        "videoScalar",
        video_scalars.TOKEN_VERSION,
        payload,
        video_scalars._TOKEN_SECRET,
    )
    legacy_router_helpers = (
        "_phase3_video_scalar_operation",
        "_phase3_video_scalar_call_structure_error",
        "_phase3_video_scalar_dry_run_errors",
        "_annotate_phase3_video_scalar_operation",
        "_validate_phase3_video_scalar_real_write",
        "_mark_phase3_video_scalar_real_operation",
        "_label_phase3_video_scalar_rejection",
        "_refresh_phase3_video_scalar_real_result",
        "_video_scalar_sha256",
        "_phase3_video_scalar_token_payload",
        "_phase3_video_scalar_confirm_token",
        "_decode_phase3_video_scalar_confirm_token",
    )
    assert not any(hasattr(write_operations, name) for name in legacy_router_helpers)


def test_video_scalars_wrapper_matches_the_legacy_fixed_secret_token_vector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(video_scalars, "_TOKEN_SECRET", b"scalar-fixed-secret")

    assert video_scalars._confirm_token(
        workspace_id="ws-1",
        cue_ref="cue-1",
        cue_id="cue-1",
        item={"profile": "video_basic"},
        operation={
            "property": "scale/x",
            "path": "scale/x",
            "mode": "saved",
            "risk_tier": "high",
            "capability_gate": "video_visual",
        },
        baseline=1.0,
        requested=1.25,
    ) == (
        "confirm:videoScalar:v1:"
        "eyJiYXNlbGluZSI6MS4wLCJiYXNlbGluZV9zaGEyNTYiOiJkMGZmNTk3NGI2YWE1MmNmNTYyYmVhNTkyMTg0MGMwMzJhODYwYTkxYTM1MTJmN2ZlOGY3NjhmNmJiZTAwNWY2IiwiY2FwYWJpbGl0eV9nYXRlIjoidmlkZW9fdmlzdWFsIiwiY3VlX2lkIjoiY3VlLTEiLCJjdWVfcmVmIjoiY3VlLTEiLCJjdWVfdHlwZSI6IlZpZGVvIiwibWNwX3NlY3JldF92ZXJzaW9uIjoxLCJtb2RlIjoic2F2ZWQiLCJvcGVyYXRpb25fa2luZCI6InZpZGVvX3BoYXNlM2Nfc2NhbGFyX3dyaXRlIiwicGF0aCI6InNjYWxlL3giLCJwcm9maWxlIjoidmlkZW9fYmFzaWMiLCJwcm9wZXJ0eSI6InNjYWxlL3giLCJyZXF1ZXN0ZWQiOjEuMjUsInJpc2tfdGllciI6ImhpZ2giLCJ2ZXJzaW9uIjoxLCJ3b3Jrc3BhY2VfaWQiOiJ3cy0xIn0:"
        "b548fb3013c51ebf5058768ca0d4f53c511bb301b8a3948a78eef2311066e41f"
    )


def test_video_appearance_uses_shared_codec_and_leaves_no_router_codec() -> None:
    payload_args = {
        "workspace_id": "ws-1",
        "cue_ref": "cue-1",
        "cue_id": "cue-1",
        "item": {"profile": "video_basic"},
        "operation": {
            "property": "blendMode",
            "path": "blendMode",
            "mode": "saved",
            "risk_tier": "high",
            "capability_gate": "video_visual",
        },
        "baseline": "Normal",
        "requested": "Multiply",
    }
    payload = video_appearance._token_payload(**payload_args)

    assert video_appearance.encode_confirm_token is token_helpers.encode_confirm_token
    assert video_appearance._confirm_token(**payload_args) == encode_confirm_token(
        "videoAppearance",
        video_appearance.TOKEN_VERSION,
        payload,
        video_appearance._TOKEN_SECRET,
    )
    legacy_router_helpers = (
        "_phase3_video_appearance_operation",
        "_phase3_video_appearance_call_structure_error",
        "_phase3_video_appearance_dry_run_errors",
        "_annotate_phase3_video_appearance_operation",
        "_validate_phase3_video_appearance_real_write",
        "_mark_phase3_video_appearance_real_operation",
        "_label_phase3_video_appearance_rejection",
        "_refresh_phase3_video_appearance_real_result",
        "_video_appearance_sha256",
        "_phase3_video_appearance_token_payload",
        "_phase3_video_appearance_confirm_token",
        "_decode_phase3_video_appearance_confirm_token",
    )
    assert not any(hasattr(write_operations, name) for name in legacy_router_helpers)


def test_video_appearance_wrapper_matches_the_legacy_fixed_secret_token_vector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(video_appearance, "_TOKEN_SECRET", b"appearance-fixed-secret")

    assert video_appearance._confirm_token(
        workspace_id="ws-1",
        cue_ref="cue-1",
        cue_id="cue-1",
        item={"profile": "video_basic"},
        operation={
            "property": "blendMode",
            "path": "blendMode",
            "mode": "saved",
            "risk_tier": "high",
            "capability_gate": "video_visual",
        },
        baseline="Normal",
        requested="Multiply",
    ) == (
        "confirm:videoAppearance:v1:"
        "eyJiYXNlbGluZSI6Ik5vcm1hbCIsImJhc2VsaW5lX3NoYTI1NiI6Ijg2MzYwM2IxZmMxYTM1OTU3MTI3OTdhZWE2YTFmMmY3YjI1ZjRlYWZkODAwZjliZTZjM2Y5OWM3NGNlYjFhZTUiLCJjYXBhYmlsaXR5X2dhdGUiOiJ2aWRlb192aXN1YWwiLCJjdWVfaWQiOiJjdWUtMSIsImN1ZV9yZWYiOiJjdWUtMSIsImN1ZV90eXBlIjoiVmlkZW8iLCJtY3Bfc2VjcmV0X3ZlcnNpb24iOjEsIm1vZGUiOiJzYXZlZCIsIm9wZXJhdGlvbl9raW5kIjoidmlkZW9fcGhhc2UzZF9hcHBlYXJhbmNlX3dyaXRlIiwicGF0aCI6ImJsZW5kTW9kZSIsInByb2ZpbGUiOiJ2aWRlb19iYXNpYyIsInByb3BlcnR5IjoiYmxlbmRNb2RlIiwicmVxdWVzdGVkIjoiTXVsdGlwbHkiLCJyaXNrX3RpZXIiOiJoaWdoIiwidmVyc2lvbiI6MSwid29ya3NwYWNlX2lkIjoid3MtMSJ9:"
        "b4fbab3b5ba971261c00dcef2465821d303fddb021ce231179bd51d5a13e5b6b"
    )


def test_video_audio_time_uses_shared_codec_and_leaves_no_router_family_helpers() -> None:
    payload_args = {
        "workspace_id": "ws-1",
        "cue_ref": "cue-1",
        "cue_id": "cue-1",
        "item": {"profile": "video_basic"},
        "operation": {
            "property": "preservePitch",
            "path": "preservePitch",
            "mode": "saved",
            "risk_tier": "high",
            "capability_gate": "audio_output",
        },
        "baseline": 1,
        "requested": False,
    }
    payload = video_audio_time._token_payload(**payload_args)

    assert video_audio_time.encode_confirm_token is token_helpers.encode_confirm_token
    assert video_audio_time._confirm_token(**payload_args) == encode_confirm_token(
        "videoAudioTime",
        video_audio_time.TOKEN_VERSION,
        payload,
        video_audio_time._TOKEN_SECRET,
    )
    legacy_router_helpers = (
        "_phase8b_video_audio_time_operation",
        "_phase8b_video_audio_time_call_structure_error",
        "_phase8b_video_audio_time_requested_value",
        "_video_audio_time_value_valid",
        "_video_audio_time_readback_value_valid",
        "_video_audio_time_canonical_value",
        "_video_audio_time_has_embedded_audio_evidence",
        "_phase8b_video_audio_time_needs_audio_evidence",
        "_phase8b_video_audio_time_token_payload",
        "_phase8b_video_audio_time_confirm_token",
        "_decode_phase8b_video_audio_time_confirm_token",
        "_phase8b_video_audio_time_dry_run_errors",
        "_annotate_phase8b_video_audio_time_operation",
        "_validate_phase8b_video_audio_time_real_write",
        "_mark_phase8b_video_audio_time_real_operation",
        "_label_phase8b_video_audio_time_rejection",
        "_refresh_phase8b_video_audio_time_real_result",
    )
    assert not any(hasattr(write_operations, name) for name in legacy_router_helpers)


def test_video_audio_time_wrapper_matches_the_legacy_fixed_secret_token_vector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(video_audio_time, "_TOKEN_SECRET", b"audio-time-fixed-secret")

    assert video_audio_time._confirm_token(
        workspace_id="ws-1",
        cue_ref="cue-1",
        cue_id="cue-1",
        item={"profile": "video_basic"},
        operation={
            "property": "preservePitch",
            "path": "preservePitch",
            "mode": "saved",
            "risk_tier": "high",
            "capability_gate": "audio_output",
        },
        baseline=1,
        requested=False,
    ) == (
        "confirm:videoAudioTime:v1:"
        "eyJiYXNlbGluZSI6dHJ1ZSwiYmFzZWxpbmVfc2hhMjU2IjoiYjViZWE0MWI2YzYyM2Y3YzA5ZjFiZjI0ZGNhZTU4ZWJhYjNjMGNkZDkwYWQ5NjZiYzQzYTQ1YjQ0ODY3ZTEyYiIsImNhcGFiaWxpdHlfZ2F0ZSI6ImF1ZGlvX291dHB1dCIsImN1ZV9pZCI6ImN1ZS0xIiwiY3VlX3JlZiI6ImN1ZS0xIiwiY3VlX3R5cGUiOiJWaWRlbyIsIm1jcF9zZWNyZXRfdmVyc2lvbiI6MSwibW9kZSI6InNhdmVkIiwib3BlcmF0aW9uX2tpbmQiOiJ2aWRlb19waGFzZThiX2F1ZGlvX3RpbWVfd3JpdGUiLCJwYXRoIjoicHJlc2VydmVQaXRjaCIsInByb2ZpbGUiOiJ2aWRlb19iYXNpYyIsInByb3BlcnR5IjoicHJlc2VydmVQaXRjaCIsInJlcXVlc3RlZCI6ZmFsc2UsInJlcXVlc3RlZF9zaGEyNTYiOiJmY2JjZjE2NTkwOGRkMThhOWU0OWY3ZmYyNzgxMDE3NmRiOGU5ZjYzYjQzNTIyMTM3NDE2NjQyNDUyMjRmOGFhIiwicmlza190aWVyIjoiaGlnaCIsInZlcnNpb24iOjEsIndvcmtzcGFjZV9pZCI6IndzLTEiLCJ3b3Jrc3BhY2VfdmFsaWRhdGlvbiI6InBvc3Rfd3JpdGVfZnJlc2hfcmVhZGJhY2tfcmVxdWlyZWQifQ:"
        "f9ca53a688e4ddf2df6d4c0187306855df3f0b875fc1359aee0bd1c32df127c8"
    )
