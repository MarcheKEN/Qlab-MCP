from __future__ import annotations

from qlab_mcp.write import operations
from qlab_mcp.write import text_basics


def test_phase3e_helpers_remain_private_operations_aliases() -> None:
    assert operations.TEXT_PHASE3E_PROPERTIES is text_basics.TEXT_PHASE3E_PROPERTIES
    assert operations._phase3e_text_basic_operation is text_basics._phase3e_text_basic_operation
    assert operations._validate_phase3e_text_basic_real_write is text_basics._validate_phase3e_text_basic_real_write
    assert operations._refresh_phase3e_text_basic_real_result is text_basics._refresh_phase3e_text_basic_real_result


def test_phase3e_token_round_trip_preserves_binding_and_canonical_values() -> None:
    cue_id = "193FB551-7985-4381-9C2D-CF4218C03FB9"
    item = {"cue_ref": cue_id, "profile": "text_basic"}
    operation = {
        "property": "text/format/fontSize",
        "path": "text/format/fontSize",
        "mode": "saved",
        "risk_tier": "high",
        "args": [72],
    }
    token = text_basics._phase3e_text_basic_confirm_token(
        workspace_id="ws-1",
        cue_ref=cue_id,
        cue_id=cue_id,
        item=item,
        operation=operation,
        baseline=48,
        requested=72,
    )
    payload, error = text_basics._decode_phase3e_text_basic_confirm_token(token)
    assert error is None
    assert payload is not None
    assert payload["operation_kind"] == "video_phase3e_text_basic_write"
    assert payload["baseline"] == 48.0
    assert payload["requested"] == 72.0


def test_phase3e_value_validation_keeps_closed_property_boundary() -> None:
    assert text_basics._text_basic_value_valid("text", "hello")
    assert text_basics._text_basic_value_valid("text/format/alignment", "center")
    assert not text_basics._text_basic_value_valid("text/format/underlineStyle", "single")
    assert not text_basics._text_basic_value_valid("text/format/fontSize", 0)
