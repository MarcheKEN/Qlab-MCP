"""Reuse compiled validators without caching observed OSC values."""

from types import SimpleNamespace

import pytest
from pydantic import BaseModel, Field, StrictBool, StrictStr, TypeAdapter

from qlab_mcp.cues.family import _section as family_section
from qlab_mcp.cues.list_models import FiniteNumber
from qlab_mcp.cues.lists import _section as list_section


class ObservedFields(BaseModel):
    model_config = {"populate_by_name": True}
    enabled: StrictBool | None = None
    level: FiniteNumber | None = None
    title: StrictStr | None = Field(default=None, validation_alias="savedTitle")


@pytest.mark.parametrize("section", [family_section, list_section])
def test_repeated_reads_reuse_validators_and_validate_fresh_values(monkeypatch, section):
    builds = []
    original = TypeAdapter.__init__

    def record(self, annotation, *args, **kwargs):
        builds.append(annotation)
        original(self, annotation, *args, **kwargs)

    monkeypatch.setattr(TypeAdapter, "__init__", record)
    # A distinct class isolates this check from validators warmed by other tests.
    class Fields(ObservedFields):
        pass

    def read(values):
        result = SimpleNamespace(errors={}, coverage=SimpleNamespace(unavailable_fields=[]))
        if section is family_section:
            parsed = section(Fields, values, result, ["enabled", "level", "savedTitle"])
        else:
            parsed = section(Fields, {"enabled": "enabled", "level": "level", "title": "savedTitle"}, values, result)
        return parsed, result

    parsed, result = read({"enabled": True, "level": -3.5, "savedTitle": "First"})
    assert parsed.enabled is True and parsed.level == -3.5 and parsed.title == "First"
    assert not result.errors
    for invalid in (True, float("nan"), float("inf")):
        parsed, result = read({"enabled": 1, "level": invalid, "savedTitle": 7})
        assert parsed.enabled is None and parsed.level is None and parsed.title is None
        assert set(result.errors) == {"enabled", "level", "savedTitle"}
    parsed, result = read({"enabled": False, "level": 0.0, "savedTitle": "Fresh"})
    assert parsed.enabled is False and parsed.level == 0.0 and parsed.title == "Fresh"
    assert not result.errors
    assert len(builds) == 3
