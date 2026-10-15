"""Evidence capture never persists confirmation tokens, including JSON scalars."""
import json
from pathlib import Path
import runpy

import pytest


redact = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "scripts/capture_move_delete.py")
)["redact"]


@pytest.mark.parametrize("value", [
    "confirm:deleteCues:v1:private-token",
    json.dumps("confirm:deleteCues:v1:private-token"),
    {"confirm_token": "private-token"},
    {"message": "Token: confirm:deleteCues:v1:private-token"},
    json.dumps({"confirm_token": "private-token"}),
    [json.dumps("confirm:deleteCues:v1:private-token")],
])
def test_redact_removes_confirmation_tokens(value):
    assert "private-token" not in json.dumps(redact(value))


@pytest.mark.parametrize("value", [None, 5, "5", '"unchanged"', "plain text"])
def test_redact_preserves_nonsensitive_scalars(value):
    assert redact(value) == value
